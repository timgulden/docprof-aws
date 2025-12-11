"""
Course Storage Handler - Phase 6: Handle course storage.

Receives OutlineReviewEvent from EventBridge.
Parses outline and stores course + sections in Aurora.
Publishes CourseStoredEvent.
"""

import json
import logging
from typing import Dict, Any

from shared.logic.courses import reduce_course_event
from shared.core.course_events import OutlineReviewEvent
from shared.command_executor import execute_command
from shared.course_state_manager import load_course_state, delete_course_state
from shared.event_publisher import (
    publish_course_stored_event,
    publish_course_error_event
)
from shared.core.commands import CreateCourseCommand, CreateSectionsCommand

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for OutlineReviewEvent.
    
    Expected event format (EventBridge):
    {
        "source": "docprof.course",
        "detail-type": "OutlineReview",
        "detail": {
            "course_id": "...",
            "reviewed_outline_text": "..."
        }
    }
    """
    try:
        # Parse EventBridge event
        detail = json.loads(event.get('detail', '{}')) if isinstance(event.get('detail'), str) else event.get('detail', {})
        course_id = detail.get('course_id')
        reviewed_outline_text = detail.get('reviewed_outline_text')
        
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
        course_event = OutlineReviewEvent(reviewed_outline_text=reviewed_outline_text or state.outline_text or "")
        
        # Process through logic layer (this will parse and create commands)
        result = reduce_course_event(state, course_event)
        
        # Execute commands (CreateCourseCommand, CreateSectionsCommand)
        stored_course_id = course_id  # Default to original course_id
        
        for command in result.commands:
            command_result = execute_command(command, result.new_state)
            
            if isinstance(command, CreateCourseCommand):
                if command_result.get('status') == 'success':
                    # Course stored - get final course_id if returned
                    stored_course_id = command_result.get('course_id', course_id)
                else:
                    error_msg = command_result.get('error', 'Unknown error')
                    logger.error(f"Course storage failed: {error_msg}")
                    publish_course_error_event(course_id, f"Course storage failed: {error_msg}")
                    return {'statusCode': 500, 'body': json.dumps({'error': error_msg})}
            
            elif isinstance(command, CreateSectionsCommand):
                if command_result.get('status') != 'success':
                    error_msg = command_result.get('error', 'Unknown error')
                    logger.error(f"Sections storage failed: {error_msg}")
                    publish_course_error_event(course_id, f"Sections storage failed: {error_msg}")
                    return {'statusCode': 500, 'body': json.dumps({'error': error_msg})}
        
        # Delete state from DynamoDB (course now in Aurora)
        delete_course_state(course_id)
        
        # Publish CourseStoredEvent
        publish_course_stored_event(course_id, stored_course_id)
        
        logger.info(f"Stored course {course_id} (final ID: {stored_course_id})")
        
        return {'statusCode': 200, 'body': json.dumps({
            'status': 'success',
            'course_id': stored_course_id
        })}
        
    except Exception as e:
        logger.error(f"Error in course storage handler: {e}", exc_info=True)
        course_id = json.loads(event.get('detail', '{}')).get('course_id') if isinstance(event.get('detail'), str) else event.get('detail', {}).get('course_id')
        if course_id:
            publish_course_error_event(course_id, f"Course storage handler error: {str(e)}")
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}
