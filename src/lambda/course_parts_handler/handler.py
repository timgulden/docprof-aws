"""
Course Parts Handler - Phase 3: Handle parts generation.

Receives PartsGeneratedEvent from EventBridge.
Parses parts and starts generating sections for first part.
Publishes PartSectionsGeneratedEvent.
"""

import json
import logging
from typing import Dict, Any

from shared.logic.courses import reduce_course_event
from shared.core.course_events import PartsGeneratedEvent
from shared.command_executor import execute_command
from shared.course_state_manager import load_course_state, save_course_state
from shared.event_publisher import publish_part_sections_generated_event, publish_course_error_event
from shared.core.commands import LLMCommand

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for PartsGeneratedEvent.
    
    Expected event format (EventBridge):
    {
        "source": "docprof.course",
        "detail-type": "PartsGenerated",
        "detail": {
            "course_id": "...",
            "parts_text": "..."
        }
    }
    """
    try:
        # Parse EventBridge event
        detail = json.loads(event.get('detail', '{}')) if isinstance(event.get('detail'), str) else event.get('detail', {})
        course_id = detail.get('course_id')
        parts_text = detail.get('parts_text')
        
        if not course_id:
            logger.error("Missing course_id in event")
            return {'statusCode': 400, 'body': json.dumps({'error': 'Missing course_id'})}
        
        if not parts_text:
            logger.error("Missing parts_text in event")
            return {'statusCode': 400, 'body': json.dumps({'error': 'Missing parts_text'})}
        
        # Load state from DynamoDB
        state = load_course_state(course_id)
        if not state:
            logger.error(f"Course state not found: {course_id}")
            publish_course_error_event(course_id, f"Course state not found: {course_id}")
            return {'statusCode': 404, 'body': json.dumps({'error': 'Course state not found'})}
        
        # Create event
        course_event = PartsGeneratedEvent(parts_text=parts_text)
        
        # Process through logic layer
        result = reduce_course_event(state, course_event)
        
        # Execute commands (LLMCommand for expand_part)
        sections_text = None
        part_index = result.new_state.current_part_index or 0
        
        for command in result.commands:
            command_result = execute_command(command, result.new_state)
            
            if isinstance(command, LLMCommand):
                if command_result.get('status') == 'success':
                    sections_text = command_result.get('content', '')
                else:
                    error_msg = command_result.get('error', 'Unknown error')
                    logger.error(f"Sections generation failed: {error_msg}")
                    publish_course_error_event(course_id, f"Sections generation failed: {error_msg}")
                    return {'statusCode': 500, 'body': json.dumps({'error': error_msg})}
        
        # Save updated state
        save_course_state(course_id, result.new_state)
        
        # Publish PartSectionsGeneratedEvent
        if sections_text:
            publish_part_sections_generated_event(course_id, sections_text, part_index)
        
        logger.info(f"Generated sections for part {part_index} of course {course_id}")
        
        return {'statusCode': 200, 'body': json.dumps({'status': 'success', 'part_index': part_index})}
        
    except Exception as e:
        logger.error(f"Error in parts handler: {e}", exc_info=True)
        course_id = json.loads(event.get('detail', '{}')).get('course_id') if isinstance(event.get('detail'), str) else event.get('detail', {}).get('course_id')
        if course_id:
            publish_course_error_event(course_id, f"Parts handler error: {str(e)}")
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}
