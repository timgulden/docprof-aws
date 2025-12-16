"""
Source Summary Generator Lambda Handler (V2 - Event-Driven)
Extracts TOC and publishes events for per-chapter processing.

This version refactors the workflow to:
1. Extract TOC
2. Publish EventBridge events for each chapter (processed separately)
3. Extract Chapter 1 text for source overview
4. Store metadata in DynamoDB for assembler

Each chapter is processed by chapter_summary_processor Lambda.
Final assembly is done by source_summary_assembler Lambda.
"""

import json
import logging
import boto3
import os
from typing import Dict, Any
from datetime import datetime

from shared.logic.source_summaries import (
    start_source_summary_generation,
    handle_toc_extracted,
)
from shared.command_executor import execute_command
from shared.response import success_response, error_response

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')
eventbridge = boto3.client('events')


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle source summary generation request (V2 - event-driven).
    
    Extracts TOC and publishes events for per-chapter processing.
    """
    try:
        # Parse event
        if event.get('source') == 'docprof.ingestion':
            detail = event.get('detail', {})
            source_id = detail.get('source_id')
            source_title = detail.get('source_title')
            author = detail.get('author')
            s3_bucket = detail.get('s3_bucket')
            s3_key = detail.get('s3_key')
        else:
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
        
        logger.info(f"Starting source summary generation (V2) for: {source_title}")
        logger.info(f"Source ID: {source_id}, S3: s3://{s3_bucket}/{s3_key}")
        
        # Step 1: Extract TOC
        result = start_source_summary_generation(
            source_id=source_id,
            source_title=source_title,
            author=author or "Unknown",
            s3_bucket=s3_bucket,
            s3_key=s3_key,
        )
        
        state = result.new_state
        if not isinstance(state, dict):
            if hasattr(state, 'model_dump'):
                state = state.model_dump()
            elif hasattr(state, 'dict'):
                state = state.dict()
            else:
                state = {}
        
        # Execute ExtractTOCCommand
        from shared.core.commands import ExtractTOCCommand
        toc_cmd = result.commands[0] if result.commands else None
        if not isinstance(toc_cmd, ExtractTOCCommand):
            return error_response("Expected ExtractTOCCommand", 500)
        
        toc_result = execute_command(toc_cmd, state)
        if toc_result.get('status') != 'success':
            return error_response(f"TOC extraction failed: {toc_result.get('error')}", 500)
        
        # Step 2: Parse TOC
        from shared.logic.source_summaries import handle_toc_extracted
        result = handle_toc_extracted(state, toc_result)
        
        new_state = result.new_state
        if not isinstance(new_state, dict):
            if hasattr(new_state, 'model_dump'):
                new_state = new_state.model_dump()
            elif hasattr(new_state, 'dict'):
                new_state = new_state.dict()
            else:
                new_state = {}
        
        toc_data = new_state.get('toc_data', {})
        chapters = toc_data.get('chapters', [])
        total_pages = new_state.get('total_pages', 0)
        
        if not chapters:
            return error_response("No chapters found in TOC", 500)
        
        logger.info(f"Extracted TOC: {len(chapters)} chapters, {total_pages} pages")
        
        # Step 3: Extract Chapter 1 text for source overview
        chapter_one_text = None
        if chapters:
            first_chapter = chapters[0]
            from shared.core.commands import ExtractChapterTextCommand
            from shared.logic.source_summaries import calculate_chapter_page_range
            
            next_chapter = chapters[1] if len(chapters) > 1 else None
            start_page, end_page = calculate_chapter_page_range(
                first_chapter,
                next_chapter,
                total_pages,
            )
            
            chapter_text_cmd = ExtractChapterTextCommand(
                s3_bucket=s3_bucket,
                s3_key=s3_key,
                start_page=start_page,
                end_page=end_page,
                chapter_title=first_chapter.get('chapter_title'),
            )
            
            chapter_text_result = execute_command(chapter_text_cmd, new_state)
            if chapter_text_result.get('status') == 'success':
                chapter_one_text = chapter_text_result.get('chapter_text', '')
                logger.info(f"Extracted Chapter 1 text: {len(chapter_one_text)} characters")
        
        # Step 4: Store metadata in DynamoDB for assembler
        table_name = f"docprof-{os.getenv('ENVIRONMENT', 'dev')}-source-summary-state"
        try:
            table = dynamodb.Table(table_name)
            table.put_item(
                Item={
                    'source_id': source_id,
                    'source_title': source_title,
                    'author': author or "Unknown",
                    'total_chapters': len(chapters),
                    'toc_data': json.dumps(toc_data),  # Store as JSON string
                    'chapter_one_text': chapter_one_text[:100000] if chapter_one_text else None,  # Limit for DynamoDB
                    's3_bucket': s3_bucket,
                    's3_key': s3_key,
                    'total_pages': total_pages,
                    'status': 'processing',
                    'chapters_completed': 0,
                    'created_at': datetime.utcnow().isoformat(),
                }
            )
            logger.info("Stored source summary state in DynamoDB")
        except Exception as e:
            logger.error(f"Failed to store state in DynamoDB: {e}")
            # Continue anyway - we can pass in events
        
        # Step 5: Publish events for each chapter
        event_bus_name = os.getenv('EVENT_BUS_NAME', '').strip() or None
        events_published = 0
        
        for chapter_index, chapter in enumerate(chapters):
            try:
                eventbridge.put_events(
                    Entries=[
                        {
                            'Source': 'docprof.ingestion',
                            'DetailType': 'ChapterSummaryRequested',
                            'Detail': json.dumps({
                                'source_id': source_id,
                                'source_title': source_title,
                                'author': author or "Unknown",
                                's3_bucket': s3_bucket,
                                's3_key': s3_key,
                                'chapter_index': chapter_index,
                                'chapter': chapter,
                                'total_pages': total_pages,
                                'toc_data': toc_data,  # Full TOC for context
                                'total_chapters': len(chapters),
                            }),
                            **({'EventBusName': event_bus_name} if event_bus_name else {}),
                        }
                    ]
                )
                events_published += 1
            except Exception as e:
                logger.error(f"Failed to publish event for chapter {chapter_index}: {e}")
        
        logger.info(f"Published {events_published}/{len(chapters)} chapter processing events")
        
        return success_response({
            'source_id': source_id,
            'status': 'toc_extracted',
            'chapters_found': len(chapters),
            'events_published': events_published,
            'message': f'TOC extracted and {events_published} chapter processing events published',
        })
        
    except Exception as e:
        logger.error(f"Error in source summary generation (V2): {e}", exc_info=True)
        return error_response(f"Source summary generation failed: {str(e)}", 500)
