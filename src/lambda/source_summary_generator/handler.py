"""
Source Summary Generator Lambda Handler
Generates source summaries as final step in ingestion pipeline.

Triggered after document processing completes.
Uses MAExpert summary generation logic adapted for Lambda/S3.
"""

import json
import logging
import boto3
from typing import Dict, Any

from shared.logic.source_summaries import (
    start_source_summary_generation,
    handle_toc_extracted,
    handle_chapter_text_extracted,
    handle_chapter_summary_generated,
    handle_source_summary_extracted,
)
from shared.command_executor import execute_command
from shared.response import success_response, error_response

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle source summary generation request.
    
    Expected event format:
    {
        "source_id": "uuid",
        "source_title": "Book Title",
        "author": "Author Name",
        "s3_bucket": "docprof-dev-source-docs",
        "s3_key": "books/uuid/title.pdf"
    }
    
    Or from EventBridge (document processing complete):
    {
        "source": "docprof.ingestion",
        "detail-type": "DocumentProcessed",
        "detail": {
            "source_id": "uuid",
            "source_title": "...",
            "author": "...",
            "s3_bucket": "...",
            "s3_key": "..."
        }
    }
    """
    try:
        # Parse event - support both direct invocation and EventBridge
        if event.get('source') == 'docprof.ingestion':
            # EventBridge format
            detail = event.get('detail', {})
            source_id = detail.get('source_id')
            source_title = detail.get('source_title')
            author = detail.get('author')
            s3_bucket = detail.get('s3_bucket')
            s3_key = detail.get('s3_key')
        else:
            # Direct invocation format
            source_id = event.get('source_id')
            source_title = event.get('source_title')
            author = event.get('author')
            s3_bucket = event.get('s3_bucket')
            s3_key = event.get('s3_key')
        
        if not all([source_id, source_title, s3_bucket, s3_key]):
            return error_response(
                "Missing required fields: source_id, source_title, s3_bucket, s3_key",
                status_code=400
            )
        
        logger.info(f"Starting source summary generation for: {source_title}")
        logger.info(f"Source ID: {source_id}, S3: s3://{s3_bucket}/{s3_key}")
        
        # Track failures and warnings for final reporting
        failed_chapters = []  # List of (chapter_index, chapter_title, error) tuples
        manual_extractions = []  # Track chapters that used manual extraction fallback
        warnings = []  # General warnings
        
        # Start summary generation pipeline
        result = start_source_summary_generation(
            source_id=source_id,
            source_title=source_title,
            author=author or "Unknown",
            s3_bucket=s3_bucket,
            s3_key=s3_key,
        )
        
        # Convert new_state to dict if it's a BaseModel
        state = result.new_state
        if not isinstance(state, dict):
            if hasattr(state, 'model_dump'):
                state = state.model_dump()
            elif hasattr(state, 'dict'):
                state = state.dict()
            elif hasattr(state, '__dict__'):
                state = state.__dict__
            else:
                # Try to convert to dict
                try:
                    state = dict(state)
                except:
                    state = {}
        max_iterations = 200  # Allow for many chapters
        iteration = 0
        
        # Process pipeline iteratively
        while result.commands and iteration < max_iterations:
            iteration += 1
            logger.debug(f"Summary pipeline iteration {iteration}")
            
            # Execute all commands
            command_results = {}
            for command in result.commands:
                logger.debug(f"Executing: {type(command).__name__}")
                cmd_result = execute_command(command, state)
                command_results[type(command).__name__] = cmd_result
            
            # Handle results based on command types
            from shared.core.commands import (
                ExtractTOCCommand,
                ExtractChapterTextCommand,
                LLMCommand,
                StoreSourceSummaryCommand,
            )
            
            if any(isinstance(cmd, ExtractTOCCommand) for cmd in result.commands):
                # TOC extracted
                toc_result = command_results.get('ExtractTOCCommand', {})
                if toc_result.get('status') == 'success':
                    result = handle_toc_extracted(state, toc_result)
                    # Convert new_state to dict
                    new_state = result.new_state
                    if hasattr(new_state, 'model_dump'):
                        state = new_state.model_dump()
                    elif hasattr(new_state, 'dict'):
                        state = new_state.dict()
                    elif not isinstance(new_state, dict):
                        state = dict(new_state) if new_state else {}
                    else:
                        state = new_state
                    # Verify toc_data is in state after TOC extraction
                    if 'toc_data' not in state:
                        logger.error(f"CRITICAL: toc_data missing after TOC extraction! State keys: {list(state.keys())}")
                        return error_response("Internal error: Table of contents data not preserved after extraction", 500)
                    logger.debug(f"TOC extracted: {len(state.get('toc_data', {}).get('chapters', []))} chapters")
                else:
                    return error_response(f"TOC extraction failed: {toc_result.get('error')}", 500)
            
            elif any(isinstance(cmd, ExtractChapterTextCommand) for cmd in result.commands):
                # Chapter text extracted
                chapter_result = command_results.get('ExtractChapterTextCommand', {})
                if chapter_result.get('status') == 'success':
                    chapter_text = chapter_result.get('chapter_text', '')
                    if state.get('toc_data') and state.get('current_chapter_index') is not None:
                        current_chapter = state['toc_data']['chapters'][state['current_chapter_index']]
                        result = handle_chapter_text_extracted(state, chapter_text, current_chapter)
                        # handle_chapter_text_extracted now preserves state including toc_data
                        new_state = result.new_state
                        if new_state and (isinstance(new_state, dict) and new_state):
                            if hasattr(new_state, 'model_dump'):
                                state = new_state.model_dump()
                            elif hasattr(new_state, 'dict'):
                                state = new_state.dict()
                            elif not isinstance(new_state, dict):
                                state = dict(new_state) if new_state else state
                            else:
                                state = new_state
                        # Otherwise keep current state (shouldn't happen now, but safe)
                    else:
                        return error_response("No chapter available for text extraction result", 500)
                else:
                    return error_response(f"Chapter text extraction failed: {chapter_result.get('error')}", 500)
            
            elif any(isinstance(cmd, LLMCommand) for cmd in result.commands):
                # LLM response received
                llm_result = command_results.get('LLMCommand', {})
                if llm_result.get('status') == 'success':
                    llm_content = llm_result.get('content', '')
                    
                    # Determine which LLM command this was
                    llm_cmd = next(cmd for cmd in result.commands if isinstance(cmd, LLMCommand))
                    task = llm_cmd.task
                    
                    if task == 'repair_json':
                        # JSON repair response - try parsing again
                        logger.info("Received repaired JSON from LLM (temperature 0.0), attempting to parse...")
                        # CRITICAL: When repair_json_with_llm returns, it has new_state={} (empty)
                        # We must NOT update state from that result - preserve existing state!
                        # The state should still have toc_data from before the repair was triggered
                        if 'toc_data' not in state:
                            logger.error(f"toc_data missing from state during JSON repair! State keys: {list(state.keys())}")
                            return error_response("Internal error: Table of contents data lost during processing", 500)
                        result = handle_chapter_summary_generated(state, llm_content)
                        
                        # Check if repair was successful
                        if not result.commands and result.ui_message and "Error" in result.ui_message:
                            logger.error(
                                f"JSON repair failed even with temperature 0.0: {result.ui_message}. "
                                f"Falling back to manual extraction."
                            )
                            # Repair failed, will fall through to manual extraction
                            # The error handling in handle_chapter_summary_generated will handle it
                            # Track this as a repair failure
                            warnings.append(f"LLM JSON repair failed for chapter {state.get('current_chapter_index', 'unknown')}")
                        else:
                            # Repair succeeded! Update state and continue
                            new_state = result.new_state
                            if not isinstance(new_state, dict):
                                if hasattr(new_state, 'model_dump'):
                                    state = new_state.model_dump()
                                elif hasattr(new_state, 'dict'):
                                    state = new_state.dict()
                                elif hasattr(new_state, '__dict__'):
                                    state = new_state.__dict__
                                else:
                                    state = dict(new_state) if new_state else {}
                            else:
                                state = new_state
                            
                            logger.info(
                                f"JSON repair successful! LLM fixed syntax errors with temperature 0.0. "
                                f"Continuing with repaired chapter summary."
                            )
                            continue
                    
                    elif task == 'generate_chapter_summary':
                        # Pass current state to handle_chapter_summary_generated
                        # It will update the state with the new chapter summary
                        # Ensure toc_data is preserved in state
                        if 'toc_data' not in state:
                            logger.error(f"toc_data missing from state during chapter summary! State keys: {list(state.keys())}")
                            return error_response("Internal error: Table of contents data lost during processing", 500)
                        result = handle_chapter_summary_generated(state, llm_content)
                        
                        # Check if there was an error (no commands and error message)
                        if not result.commands and result.ui_message and "Error" in result.ui_message:
                            # Track the failure
                            current_idx = state.get('current_chapter_index', -1)
                            current_chapter = None
                            if state.get('toc_data') and current_idx >= 0 and current_idx < len(state.get('toc_data', {}).get('chapters', [])):
                                current_chapter = state['toc_data']['chapters'][current_idx]
                            
                            chapter_info = {
                                'index': current_idx,
                                'title': current_chapter.get('title', 'Unknown') if current_chapter else 'Unknown',
                                'error': result.ui_message
                            }
                            failed_chapters.append(chapter_info)
                            
                            logger.error(
                                f"Chapter summary generation failed for chapter {current_idx} "
                                f"({chapter_info['title']}): {result.ui_message}"
                            )
                            
                            # Check if manual extraction was attempted (indicated by specific error message)
                            if "Could not parse" in result.ui_message or "Could not extract" in result.ui_message:
                                logger.warning(
                                    f"CRITICAL: Chapter {current_idx} ({chapter_info['title']}) failed JSON parsing "
                                    f"even with manual extraction fallback. This indicates a serious LLM output quality issue."
                                )
                                
                                # Decide: fail loudly or continue with degraded quality?
                                # For now, continue but track it prominently
                                # Try to move to next chapter if possible
                                if state.get('toc_data') and state.get('current_chapter_index') is not None:
                                    current_idx = state.get('current_chapter_index', 0)
                                    if current_idx + 1 < len(state['toc_data']['chapters']):
                                        logger.warning(
                                            f"Continuing to next chapter despite failure. "
                                            f"Failed chapters so far: {len(failed_chapters)}"
                                        )
                                        # Import here to avoid circular import
                                        from shared.logic.source_summaries import process_chapter
                                        state['current_chapter_index'] = current_idx + 1
                                        next_chapter = state['toc_data']['chapters'][current_idx + 1]
                                        result = process_chapter(state, next_chapter, current_idx + 1)
                                        new_state = result.new_state
                                        if not isinstance(new_state, dict):
                                            if hasattr(new_state, 'model_dump'):
                                                state = new_state.model_dump()
                                            elif hasattr(new_state, 'dict'):
                                                state = new_state.dict()
                                            else:
                                                state = dict(new_state) if new_state else {}
                                        else:
                                            state = new_state
                                        continue
                            
                            # If we can't continue, fail loudly
                            return error_response(
                                f"Chapter summary generation failed: {result.ui_message}. "
                                f"Failed chapters: {len(failed_chapters)}",
                                500
                            )
                        
                        # Check if manual extraction was used (by checking logs or result metadata)
                        # We'll detect this by checking if the chapter summary has minimal fields
                        # This is a best-effort detection
                        if state.get('chapter_summaries'):
                            latest_summary = state['chapter_summaries'][-1]
                            # If summary exists but has minimal fields, it might be from manual extraction
                            # We'll track this separately if needed
                        
                        # CRITICAL: If result has commands (like repair_json), it means we're not done yet
                        # and the new_state might be empty. We should preserve existing state in that case.
                        if result.commands:
                            # Result has commands (e.g., repair_json) - preserve state, don't update from empty new_state
                            # The state will be updated later when the command completes
                            logger.debug(f"Result has {len(result.commands)} command(s), preserving state")
                            # Don't update state - continue loop to execute the command
                        else:
                            # No commands - update state from result
                            new_state = result.new_state
                            if not isinstance(new_state, dict):
                                if hasattr(new_state, 'model_dump'):
                                    state = new_state.model_dump()
                                elif hasattr(new_state, 'dict'):
                                    state = new_state.dict()
                                elif hasattr(new_state, '__dict__'):
                                    state = new_state.__dict__
                                else:
                                    state = dict(new_state) if new_state else {}
                            else:
                                state = new_state
                    elif task == 'extract_source_summary':
                        result = handle_source_summary_extracted(state, llm_content)
                        new_state = result.new_state
                        if hasattr(new_state, 'model_dump'):
                            state = new_state.model_dump()
                        elif hasattr(new_state, 'dict'):
                            state = new_state.dict()
                        elif not isinstance(new_state, dict):
                            state = dict(new_state) if new_state else {}
                        else:
                            state = new_state
                    else:
                        return error_response(f"Unknown LLM task: {task}", 500)
                else:
                    return error_response(f"LLM command failed: {llm_result.get('error')}", 500)
            
            elif any(isinstance(cmd, StoreSourceSummaryCommand) for cmd in result.commands):
                # Summary stored - pipeline complete
                store_result = command_results.get('StoreSourceSummaryCommand', {})
                if store_result.get('status') == 'success':
                    logger.info(f"Source summary stored successfully: {store_result.get('summary_id')}")
                    
                    # Publish SourceSummaryStored event to trigger embedding generation
                    try:
                        import os
                        event_bus_name = os.getenv('EVENT_BUS_NAME', '').strip() or None  # Use default bus if empty
                        eventbridge = boto3.client('events')
                        
                        eventbridge.put_events(
                            Entries=[
                                {
                                    'Source': 'docprof.ingestion',
                                    'DetailType': 'SourceSummaryStored',
                                    'Detail': json.dumps({
                                        'source_id': source_id,
                                        'summary_id': store_result.get('summary_id'),
                                        'chapters_processed': len(state.get('chapter_summaries', [])),
                                    }),
                                    **({'EventBusName': event_bus_name} if event_bus_name else {}),
                                }
                            ]
                        )
                        logger.info("Published SourceSummaryStored event for embedding generation")
                        event_published = True
                    except Exception as e:
                        logger.error(
                            f"CRITICAL: Failed to publish SourceSummaryStored event: {e}. "
                            f"Embedding generation may not be triggered automatically.",
                            exc_info=True
                        )
                        warnings.append(f"Event publishing failed: {str(e)}")
                        event_published = False
                        # Don't fail the entire operation, but make it very visible
                    
                    # Build comprehensive response with failure tracking
                    manual_count = len([s for s in state.get('chapter_summaries', []) 
                                        if s.get('_extraction_method') == 'manual_fallback'])
                    
                    response_data = {
                        'source_id': source_id,
                        'summary_id': store_result.get('summary_id'),
                        'chapters_processed': len(state.get('chapter_summaries', [])),
                        'status': 'complete',
                        'statistics': {
                            'total_chapters_processed': len(state.get('chapter_summaries', [])),
                            'failed_chapters': len(failed_chapters),
                            'manual_extractions': manual_count,
                            'event_published': event_published,
                        }
                    }
                    
                    # Add detailed failure information if any failures occurred
                    if failed_chapters:
                        response_data['failed_chapters'] = failed_chapters
                        logger.warning(
                            f"Summary generation completed with {len(failed_chapters)} failed chapters. "
                            f"Failed: {[f.get('title', 'Unknown') for f in failed_chapters]}"
                        )
                    
                    if warnings:
                        response_data['warnings'] = warnings
                        logger.warning(f"Summary generation completed with {len(warnings)} warnings: {warnings}")
                    
                    # Log final statistics
                    if manual_count > 0:
                        logger.warning(
                            f"QUALITY WARNING: {manual_count} chapters used manual extraction fallback. "
                            f"This indicates LLM JSON output quality issues that should be investigated."
                        )
                    
                    if len(failed_chapters) > 0:
                        logger.error(
                            f"FAILURE SUMMARY: {len(failed_chapters)} chapters failed completely. "
                            f"Summary is incomplete."
                        )
                    
                    return success_response(response_data)
                else:
                    return error_response(f"Failed to store summary: {store_result.get('error')}", 500)
            
            else:
                return error_response(f"Unknown command type in pipeline", 500)
        
        if iteration >= max_iterations:
            error_msg = (
                f"Pipeline exceeded max iterations ({max_iterations}). "
                f"Processed {len(state.get('chapter_summaries', []))} chapters. "
                f"Failed chapters: {len(failed_chapters)}"
            )
            if failed_chapters:
                error_msg += f". Failed: {[f['title'] for f in failed_chapters]}"
            return error_response(error_msg, 500)

        # Pipeline completed without storing summary
        error_msg = (
            f"Pipeline completed without storing summary. "
            f"Processed {len(state.get('chapter_summaries', []))} chapters. "
            f"Failed chapters: {len(failed_chapters)}"
        )
        if failed_chapters:
            error_msg += f". Failed: {[f['title'] for f in failed_chapters]}"
        return error_response(error_msg, 500)
        
    except Exception as e:
        logger.error(f"Error in source summary generator: {e}", exc_info=True)
        return error_response(f"Internal server error: {str(e)}", status_code=500)
