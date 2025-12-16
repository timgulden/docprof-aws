"""
Source Summary Assembler Lambda Handler
Collects all chapter summaries and assembles the final source summary.

Triggered when all chapters are processed (via EventBridge or manual invocation).
Reads chapter summaries from DynamoDB and assembles the final JSON.
"""

import json
import logging
import boto3
import os
from typing import Dict, Any, List
from datetime import datetime

from shared.logic.source_summaries import (
    build_source_overview_prompt_variables,
    assemble_source_summary_json,
)
from shared.core.commands import LLMCommand, StoreSourceSummaryCommand
from shared.command_executor import execute_command
from shared.response import success_response, error_response

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Assemble final source summary from all chapter summaries.
    
    Expected event format:
    {
        "source_id": "uuid",
        "source_title": "Book Title",
        "author": "Author Name",
        "total_chapters": 43,
        "chapter_one_text": "..." (optional, for source overview)
    }
    
    Or from EventBridge (when last chapter completes):
    {
        "source": "docprof.ingestion",
        "detail-type": "ChapterSummaryCompleted",
        "detail": {
            "source_id": "...",
            "total_chapters": 43,
            ...
        }
    }
    """
    try:
        # Parse event
        if event.get('source') == 'docprof.ingestion':
            detail = event.get('detail', {})
            source_id = detail.get('source_id')
            source_title = detail.get('source_title')
            author = detail.get('author')
            total_chapters = detail.get('total_chapters')
            chapter_one_text = detail.get('chapter_one_text')
        else:
            source_id = event.get('source_id')
            source_title = event.get('source_title')
            author = event.get('author')
            total_chapters = event.get('total_chapters')
            chapter_one_text = event.get('chapter_one_text')
        
        if not source_id:
            return error_response("Missing required field: source_id", 400)
        
        logger.info(f"Assembling source summary for: {source_id}")
        
        # Get metadata from state table if not provided
        if not source_title or not author or not total_chapters:
            state_table_name = f"docprof-{os.getenv('ENVIRONMENT', 'dev')}-source-summary-state"
            try:
                state_table = dynamodb.Table(state_table_name)
                response = state_table.get_item(Key={'source_id': source_id})
                if 'Item' in response:
                    item = response['Item']
                    source_title = source_title or item.get('source_title')
                    author = author or item.get('author')
                    total_chapters = total_chapters or item.get('total_chapters')
                    chapter_one_text = chapter_one_text or item.get('chapter_one_text')
            except Exception as e:
                logger.warning(f"Failed to read state from DynamoDB: {e}")
        
        # Read all chapter summaries from DynamoDB
        table_name = f"docprof-{os.getenv('ENVIRONMENT', 'dev')}-chapter-summaries"
        try:
            table = dynamodb.Table(table_name)
            
            # Query all chapters for this source_id
            response = table.query(
                KeyConditionExpression='source_id = :sid',
                ExpressionAttributeValues={':sid': source_id},
            )
            
            chapter_items = response.get('Items', [])
            
            # Sort by chapter_index
            chapter_items.sort(key=lambda x: x.get('chapter_index', 0))
            
            logger.info(f"Found {len(chapter_items)} chapter summaries in DynamoDB")
            
            if len(chapter_items) == 0:
                return error_response("No chapter summaries found in DynamoDB", 404)
            
            # Extract chapter summaries (parse JSON if stored as string)
            chapter_summaries = []
            for item in chapter_items:
                summary = item.get('chapter_summary')
                if summary:
                    if isinstance(summary, str):
                        try:
                            summary = json.loads(summary)
                        except:
                            pass
                    chapter_summaries.append(summary)
            
            if len(chapter_summaries) != len(chapter_items):
                logger.warning(f"Some chapters missing summaries: {len(chapter_summaries)}/{len(chapter_items)}")
            
            # Check if we have all chapters
            if total_chapters and len(chapter_summaries) < total_chapters:
                logger.warning(
                    f"Only {len(chapter_summaries)}/{total_chapters} chapters processed. "
                    f"Proceeding with partial summary."
                )
        
        except Exception as e:
            logger.error(f"Failed to read chapter summaries from DynamoDB: {e}")
            return error_response(f"Failed to read chapter summaries: {str(e)}", 500)
        
        # Extract source overview from Chapter 1 if available
        if chapter_one_text:
            logger.info("Extracting source overview from Chapter 1...")
            prompt_variables = build_source_overview_prompt_variables(chapter_one_text)
            
            # Call LLM to extract overview
            from shared.command_executor import execute_command
            llm_cmd = LLMCommand(
                prompt_name="source_summaries.extract_overview",
                prompt_variables=prompt_variables,
                task="extract_source_summary",
                temperature=0.7,
                max_tokens=500,
            )
            
            llm_result = execute_command(llm_cmd, {})
            if llm_result.get('status') == 'success':
                source_summary_text = llm_result.get('content', '').strip()
            else:
                logger.warning("Failed to extract source overview from Chapter 1, using fallback")
                source_summary_text = f"{source_title or 'Unknown'} by {author or 'Unknown'} covers {len(chapter_summaries)} chapters."
        else:
            logger.info("No Chapter 1 text provided, using simple summary")
            source_summary_text = f"{source_title or 'Unknown'} by {author or 'Unknown'} covers {len(chapter_summaries)} chapters."
        
        # Assemble final JSON
        summary_json = assemble_source_summary_json(
            source_title or "Unknown",
            author or "Unknown",
            chapter_summaries,
            source_summary_text,
        )
        
        # Store final summary
        from shared.command_executor import execute_command
        store_cmd = StoreSourceSummaryCommand(
            source_id=source_id,
            summary_json=summary_json,
        )
        
        store_result = execute_command(store_cmd, {})
        
        if store_result.get('status') != 'success':
            return error_response(f"Failed to store source summary: {store_result.get('error')}", 500)
        
        logger.info(f"Source summary assembled and stored: {store_result.get('summary_id')}")
        
        # Publish SourceSummaryStored event for embedding generation
        try:
            eventbridge = boto3.client('events')
            event_bus_name = os.getenv('EVENT_BUS_NAME', '').strip() or None
            
            eventbridge.put_events(
                Entries=[
                    {
                        'Source': 'docprof.ingestion',
                        'DetailType': 'SourceSummaryStored',
                        'Detail': json.dumps({
                            'source_id': source_id,
                            'summary_id': store_result.get('summary_id'),
                            'chapters_processed': len(chapter_summaries),
                        }),
                        **({'EventBusName': event_bus_name} if event_bus_name else {}),
                    }
                ]
            )
            logger.info("Published SourceSummaryStored event for embedding generation")
        except Exception as e:
            logger.warning(f"Failed to publish SourceSummaryStored event: {e}")
        
        return success_response({
            'source_id': source_id,
            'summary_id': store_result.get('summary_id'),
            'chapters_processed': len(chapter_summaries),
            'status': 'completed',
        })
        
    except Exception as e:
        logger.error(f"Error assembling source summary: {e}", exc_info=True)
        return error_response(f"Source summary assembly failed: {str(e)}", 500)
