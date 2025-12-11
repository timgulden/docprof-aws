"""
Course Embedding Handler - Phase 1: Handle embedding generation.

Receives EmbeddingGeneratedEvent from EventBridge.
Searches book summaries and publishes BookSummariesFoundEvent.
"""

import json
import logging
from typing import Dict, Any

from shared.logic.courses import reduce_course_event
from shared.core.course_events import EmbeddingGeneratedEvent
from shared.command_executor import execute_command
from shared.course_state_manager import load_course_state, save_course_state
from shared.event_publisher import publish_book_summaries_found_event, publish_course_error_event
from shared.core.commands import SearchBookSummariesCommand

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for EmbeddingGeneratedEvent.
    
    Expected event format (EventBridge):
    {
        "source": "docprof.course",
        "detail-type": "EmbeddingGenerated",
        "detail": {
            "course_id": "...",
            "embedding": [...],
            "task": "..."
        }
    }
    """
    try:
        # Parse EventBridge event
        detail = json.loads(event.get('detail', '{}')) if isinstance(event.get('detail'), str) else event.get('detail', {})
        course_id = detail.get('course_id')
        embedding = detail.get('embedding')
        
        if not course_id:
            logger.error("Missing course_id in event")
            return {'statusCode': 400, 'body': json.dumps({'error': 'Missing course_id'})}
        
        if not embedding:
            logger.error("Missing embedding in event")
            return {'statusCode': 400, 'body': json.dumps({'error': 'Missing embedding'})}
        
        # Load state from DynamoDB
        state = load_course_state(course_id)
        if not state:
            logger.error(f"Course state not found: {course_id}")
            publish_course_error_event(course_id, f"Course state not found: {course_id}")
            return {'statusCode': 404, 'body': json.dumps({'error': 'Course state not found'})}
        
        # Create event
        course_event = EmbeddingGeneratedEvent(embedding=embedding)
        
        # Process through logic layer
        result = reduce_course_event(state, course_event)
        
        # Execute commands (SearchBookSummariesCommand)
        books = []
        for command in result.commands:
            command_result = execute_command(command, result.new_state)
            
            if isinstance(command, SearchBookSummariesCommand):
                if command_result.get('status') == 'success':
                    books = command_result.get('books', [])
                else:
                    error_msg = command_result.get('error', 'Unknown error')
                    logger.error(f"Book search failed: {error_msg}")
                    publish_course_error_event(course_id, f"Book search failed: {error_msg}")
                    return {'statusCode': 500, 'body': json.dumps({'error': error_msg})}
        
        # Save updated state
        save_course_state(course_id, result.new_state)
        
        # Publish BookSummariesFoundEvent
        publish_book_summaries_found_event(course_id, books)
        
        logger.info(f"Processed embedding for course {course_id}, found {len(books)} books")
        
        return {'statusCode': 200, 'body': json.dumps({'status': 'success', 'books_count': len(books)})}
        
    except Exception as e:
        logger.error(f"Error in embedding handler: {e}", exc_info=True)
        course_id = json.loads(event.get('detail', '{}')).get('course_id') if isinstance(event.get('detail'), str) else event.get('detail', {}).get('course_id')
        if course_id:
            publish_course_error_event(course_id, f"Embedding handler error: {str(e)}")
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}
