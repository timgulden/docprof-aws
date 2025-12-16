"""
Course Book Search Handler - Phase 2: Handle book summaries found.

Receives BookSummariesFoundEvent from EventBridge.
Generates course parts structure and publishes PartsGeneratedEvent.
"""

import json
import logging
from typing import Dict, Any

from shared.logic.courses import reduce_course_event
from shared.core.course_events import BookSummariesFoundEvent
from shared.command_executor import execute_command
from shared.course_state_manager import load_course_state, save_course_state
from shared.event_publisher import publish_parts_generated_event, publish_course_error_event
from shared.core.commands import LLMCommand

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for BookSummariesFoundEvent.
    
    Expected event format (EventBridge):
    {
        "source": "docprof.course",
        "detail-type": "BookSummariesFound",
        "detail": {
            "course_id": "...",
            "books": [...]
        }
    }
    """
    try:
        # Parse EventBridge event
        detail = json.loads(event.get('detail', '{}')) if isinstance(event.get('detail'), str) else event.get('detail', {})
        course_id = detail.get('course_id')
        books = detail.get('books', [])
        
        if not course_id:
            logger.error("Missing course_id in event")
            return {'statusCode': 400, 'body': json.dumps({'error': 'Missing course_id'})}
        
        # Load state from DynamoDB
        state = load_course_state(course_id)
        if not state:
            logger.error(f"Course state not found: {course_id}")
            publish_course_error_event(course_id, f"Course state not found: {course_id}")
            return {'statusCode': 404, 'body': json.dumps({'error': 'Course state not found'})}
        
        # Create event
        course_event = BookSummariesFoundEvent(books=books)
        
        # Process through logic layer
        result = reduce_course_event(state, course_event)
        
        logger.info(f"Logic returned {len(result.commands)} commands")
        
        # Execute commands (LLMCommand for generate_parts)
        parts_text = None
        for idx, command in enumerate(result.commands):
            logger.info(f"Executing command {idx+1}/{len(result.commands)}: {type(command).__name__}")
            command_result = execute_command(command, result.new_state)
            logger.info(f"Command result: status={command_result.get('status')}, has_content={'content' in command_result}")
            
            if isinstance(command, LLMCommand):
                if command_result.get('status') == 'success':
                    parts_text = command_result.get('content', '')
                    model_switch_notification = command_result.get('model_switch_notification')
                    if model_switch_notification:
                        logger.warning(f"Model switch during parts generation: {model_switch_notification}")
                        # Log to CloudWatch - user can see this in logs
                        # For async operations, we rely on logging rather than API responses
                    logger.info(f"LLM returned parts_text (length: {len(parts_text) if parts_text else 0})")
                else:
                    error_msg = command_result.get('error', 'Unknown error')
                    logger.error(f"Parts generation failed: {error_msg}")
                    publish_course_error_event(course_id, f"Parts generation failed: {error_msg}")
                    return {'statusCode': 500, 'body': json.dumps({'error': error_msg})}
        
        # Save updated state
        save_course_state(course_id, result.new_state)
        
        # Publish PartsGeneratedEvent
        if parts_text:
            publish_parts_generated_event(course_id, parts_text)
        
        logger.info(f"Generated parts for course {course_id}")
        
        return {'statusCode': 200, 'body': json.dumps({'status': 'success'})}
        
    except Exception as e:
        logger.error(f"Error in book search handler: {e}", exc_info=True)
        course_id = json.loads(event.get('detail', '{}')).get('course_id') if isinstance(event.get('detail'), str) else event.get('detail', {}).get('course_id')
        if course_id:
            publish_course_error_event(course_id, f"Book search handler error: {str(e)}")
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}
