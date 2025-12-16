"""
Chapter Summary Processor Lambda Handler
Processes a single chapter: extracts text and generates summary.

This Lambda is invoked per chapter to avoid 15-minute timeout limits.
Each chapter is processed independently and results are stored in DynamoDB.
"""

import json
import logging
import boto3
import os
from typing import Dict, Any
from datetime import datetime

from shared.logic.source_summaries import (
    process_chapter,
    handle_chapter_text_extracted,
    handle_chapter_summary_generated,
)
from shared.command_executor import execute_command
from shared.response import success_response, error_response
from shared.core.state import LogicResult

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Process a single chapter for source summary generation.
    
    Expected event format:
    {
        "source_id": "uuid",
        "source_title": "Book Title",
        "author": "Author Name",
        "s3_bucket": "docprof-dev-source-docs",
        "s3_key": "books/uuid/title.pdf",
        "chapter_index": 0,  # 0-based index
        "chapter": {
            "chapter_number": 1,
            "chapter_title": "Chapter Title",
            "page_number": 54,
            "sections": [...]
        },
        "total_pages": 1321,
        "toc_data": {...}  # Full TOC structure for context
    }
    
    Or from EventBridge:
    {
        "source": "docprof.ingestion",
        "detail-type": "ChapterSummaryRequested",
        "detail": {
            "source_id": "...",
            "chapter_index": 0,
            ...
        }
    }
    """
    try:
        # Parse event - support both direct invocation and EventBridge
        if event.get('source') == 'docprof.ingestion':
            detail = event.get('detail', {})
            source_id = detail.get('source_id')
            chapter_index = detail.get('chapter_index')
            chapter = detail.get('chapter')
            source_title = detail.get('source_title')
            author = detail.get('author')
            s3_bucket = detail.get('s3_bucket')
            s3_key = detail.get('s3_key')
            total_pages = detail.get('total_pages')
            toc_data = detail.get('toc_data')
        else:
            source_id = event.get('source_id')
            chapter_index = event.get('chapter_index')
            chapter = event.get('chapter')
            source_title = event.get('source_title')
            author = event.get('author')
            s3_bucket = event.get('s3_bucket')
            s3_key = event.get('s3_key')
            total_pages = event.get('total_pages')
            toc_data = event.get('toc_data')
        
        if not all([source_id, chapter_index is not None, chapter, s3_bucket, s3_key]):
            return error_response(
                "Missing required fields: source_id, chapter_index, chapter, s3_bucket, s3_key",
                status_code=400
            )
        
        logger.info(
            f"Processing chapter {chapter.get('chapter_number')}: {chapter.get('chapter_title')} "
            f"(index {chapter_index})"
        )
        
        # Build state for this chapter
        state = {
            "source_id": source_id,
            "source_title": source_title or "Unknown",
            "author": author or "Unknown",
            "s3_bucket": s3_bucket,
            "s3_key": s3_key,
            "total_pages": total_pages or 0,
            "toc_data": toc_data or {},
            "current_chapter_index": chapter_index,
        }
        
        # Process this chapter
        result = process_chapter(state, chapter, chapter_index)
        
        # Execute commands sequentially
        current_state = state
        max_iterations = 10  # Extract text, generate summary, maybe repair JSON
        iteration = 0
        
        while result.commands and iteration < max_iterations:
            iteration += 1
            logger.debug(f"Chapter processing iteration {iteration}")
            
            # Handle commands that this processor should NOT execute
            # In particular, we skip extract_source_summary tasks here because
            # source-level summaries are handled by the source_summary_assembler Lambda.
            from shared.core.commands import (
                ExtractChapterTextCommand,
                LLMCommand,
            )
            if (
                len(result.commands) == 1
                and isinstance(result.commands[0], LLMCommand)
                and getattr(result.commands[0], "task", "") == "extract_source_summary"
            ):
                logger.info(
                    "Skipping extract_source_summary task in chapter_summary_processor "
                    "- source-level summaries are handled by source_summary_assembler."
                )
                # Stop processing further commands; we've already stored the chapter summary
                result = LogicResult(
                    new_state=current_state,
                    commands=[],
                    ui_message="Chapter summary complete; source summary will be handled by assembler.",
                )
                break
            
            # Execute all commands
            command_results = {}
            for command in result.commands:
                logger.debug(f"Executing: {type(command).__name__}")
                cmd_result = execute_command(command, current_state)
                command_results[type(command).__name__] = cmd_result
            
            # Handle results
            if any(isinstance(cmd, ExtractChapterTextCommand) for cmd in result.commands):
                chapter_result = command_results.get('ExtractChapterTextCommand', {})
                if chapter_result.get('status') == 'success':
                    chapter_text = chapter_result.get('chapter_text', '')
                    result = handle_chapter_text_extracted(current_state, chapter_text, chapter)
                    new_state = result.new_state
                    if isinstance(new_state, dict):
                        current_state = new_state
                    elif hasattr(new_state, 'model_dump'):
                        current_state = new_state.model_dump()
                    elif hasattr(new_state, 'dict'):
                        current_state = new_state.dict()
                    else:
                        current_state = dict(new_state) if new_state else current_state
                else:
                    return error_response(
                        f"Chapter text extraction failed: {chapter_result.get('error')}",
                        500
                    )
            
            elif any(isinstance(cmd, LLMCommand) for cmd in result.commands):
                llm_result = command_results.get('LLMCommand', {})
                if llm_result.get('status') == 'success':
                    llm_content = llm_result.get('content', '')
                    llm_cmd = next(cmd for cmd in result.commands if isinstance(cmd, LLMCommand))
                    task = llm_cmd.task
                    
                    if task == 'generate_chapter_summary':
                        result = handle_chapter_summary_generated(current_state, llm_content)
                        new_state = result.new_state
                        if isinstance(new_state, dict):
                            current_state = new_state
                        elif hasattr(new_state, 'model_dump'):
                            current_state = new_state.model_dump()
                        elif hasattr(new_state, 'dict'):
                            current_state = new_state.dict()
                        else:
                            current_state = dict(new_state) if new_state else current_state
                        
                        # IMPORTANT: Stop after processing this chapter's summary
                        # The logic layer may return commands to process the next chapter,
                        # but this Lambda handles ONLY ONE chapter per invocation
                        # Clear any remaining commands to exit the loop
                        result = LogicResult(
                            new_state=current_state,
                            commands=[],
                            ui_message="Chapter summary generated"
                        )
                    elif task == 'repair_json':
                        # JSON repair - try parsing again
                        result = handle_chapter_summary_generated(current_state, llm_content)
                        new_state = result.new_state
                        if isinstance(new_state, dict):
                            current_state = new_state
                        elif hasattr(new_state, 'model_dump'):
                            current_state = new_state.model_dump()
                        elif hasattr(new_state, 'dict'):
                            current_state = new_state.dict()
                        else:
                            current_state = dict(new_state) if new_state else current_state
                        continue
                    else:
                        return error_response(f"Unknown LLM task: {task}", 500)
                else:
                    return error_response(f"LLM command failed: {llm_result.get('error')}", 500)
            else:
                # Unknown command type
                return error_response(f"Unknown command type in result", 500)
        
        # Get the final chapter summary
        # NOTE: This Lambda processes ONLY ONE chapter per invocation
        # If the logic returns commands to process another chapter, we ignore them
        # (the orchestrator handles multi-chapter workflows)
        chapter_summaries = current_state.get('chapter_summaries', [])
        if not chapter_summaries:
            return error_response("No chapter summary generated", 500)
        
        # Get the chapter summary (should only be 1 since we stop after processing one chapter)
        if len(chapter_summaries) != 1:
            logger.warning(
                f"Expected 1 chapter summary, found {len(chapter_summaries)}. "
                f"Taking the first one and overriding metadata."
            )
        
        chapter_summary = chapter_summaries[0] if chapter_summaries else None
        if not chapter_summary:
            return error_response("No chapter summary found in state", 500)
        
        # CRITICAL FIX: Override chapter_number and chapter_title with event values
        # The LLM sometimes returns different values than requested, causing mismatches
        # We trust the event data (what we asked to process) over the LLM output
        if isinstance(chapter_summary, dict):
            chapter_summary['chapter_number'] = chapter.get('chapter_number')
            chapter_summary['chapter_title'] = chapter.get('chapter_title')
            logger.info(
                f"Ensured summary metadata matches event: Ch{chapter.get('chapter_number')} - "
                f"{chapter.get('chapter_title')}"
            )
        
        # Store chapter summary in DynamoDB for later assembly
        table_name = f"docprof-{os.getenv('ENVIRONMENT', 'dev')}-chapter-summaries"
        try:
            table = dynamodb.Table(table_name)
            table.put_item(
                Item={
                    'source_id': source_id,
                    'chapter_index': chapter_index,
                    'chapter_number': chapter.get('chapter_number'),
                    'chapter_title': chapter.get('chapter_title'),
                    'chapter_summary': json.dumps(chapter_summary) if isinstance(chapter_summary, dict) else chapter_summary,
                    'status': 'completed',
                    'timestamp': datetime.utcnow().isoformat(),
                }
            )
            logger.info(f"Stored chapter summary for chapter {chapter.get('chapter_number')}")
        except Exception as e:
            logger.error(f"Failed to store chapter summary in DynamoDB: {e}")
            # Continue anyway - we'll return the summary
        
        # Update source summary state to track completion
        state_table_name = f"docprof-{os.getenv('ENVIRONMENT', 'dev')}-source-summary-state"
        try:
            state_table = dynamodb.Table(state_table_name)
            # Increment chapters_completed counter
            state_table.update_item(
                Key={'source_id': source_id},
                UpdateExpression='ADD chapters_completed :inc',
                ExpressionAttributeValues={':inc': 1},
            )
            
            # Check if all chapters are done
            response = state_table.get_item(Key={'source_id': source_id})
            if 'Item' in response:
                item = response['Item']
                chapters_completed = item.get('chapters_completed', 0)
                total_chapters = item.get('total_chapters', 0)
                
                if chapters_completed >= total_chapters:
                    logger.info(f"All {total_chapters} chapters completed! Triggering assembler...")
                    # Trigger assembler
                    try:
                        event_bus_name = os.getenv('EVENT_BUS_NAME', '').strip() or None
                        eventbridge.put_events(
                            Entries=[
                                {
                                    'Source': 'docprof.ingestion',
                                    'DetailType': 'AllChaptersCompleted',
                                    'Detail': json.dumps({
                                        'source_id': source_id,
                                        'source_title': item.get('source_title'),
                                        'author': item.get('author'),
                                        'total_chapters': total_chapters,
                                        'chapter_one_text': item.get('chapter_one_text'),
                                    }),
                                    **({'EventBusName': event_bus_name} if event_bus_name else {}),
                                }
                            ]
                        )
                        logger.info("Published AllChaptersCompleted event")
                    except Exception as e:
                        logger.error(f"Failed to publish AllChaptersCompleted event: {e}")
        except Exception as e:
            logger.warning(f"Failed to update source summary state: {e}")
        
        # Publish event that this chapter is complete
        try:
            eventbridge = boto3.client('events')
            event_bus_name = os.getenv('EVENT_BUS_NAME', '').strip() or None
            
            eventbridge.put_events(
                Entries=[
                    {
                        'Source': 'docprof.ingestion',
                        'DetailType': 'ChapterSummaryCompleted',
                        'Detail': json.dumps({
                            'source_id': source_id,
                            'chapter_index': chapter_index,
                            'chapter_number': chapter.get('chapter_number'),
                            'total_chapters': len(toc_data.get('chapters', [])) if toc_data else 0,
                        }),
                        **({'EventBusName': event_bus_name} if event_bus_name else {}),
                    }
                ]
            )
            logger.info("Published ChapterSummaryCompleted event")
        except Exception as e:
            logger.warning(f"Failed to publish ChapterSummaryCompleted event: {e}")
        
        return success_response({
            'source_id': source_id,
            'chapter_index': chapter_index,
            'chapter_number': chapter.get('chapter_number'),
            'chapter_title': chapter.get('chapter_title'),
            'status': 'completed',
            'chapter_summary': chapter_summary,
        })
        
    except Exception as e:
        logger.error(f"Error processing chapter: {e}", exc_info=True)
        return error_response(f"Chapter processing failed: {str(e)}", 500)
