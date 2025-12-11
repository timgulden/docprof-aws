"""
Course Sections Handler - Phase 4: Handle part sections generation.

Receives PartSectionsGeneratedEvent from EventBridge.
Appends sections to outline and either:
- Continues with next part (publishes PartSectionsGeneratedEvent again)
- Or completes all parts (publishes AllPartsCompleteEvent)
"""

import json
import logging
from typing import Dict, Any

from shared.logic.courses import reduce_course_event
from shared.core.course_events import PartSectionsGeneratedEvent
from shared.command_executor import execute_command
from shared.course_state_manager import load_course_state, save_course_state
from shared.event_publisher import (
    publish_part_sections_generated_event,
    publish_all_parts_complete_event,
    publish_course_error_event
)
from shared.core.commands import LLMCommand

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for PartSectionsGeneratedEvent.
    
    Expected event format (EventBridge):
    {
        "source": "docprof.course",
        "detail-type": "PartSectionsGenerated",
        "detail": {
            "course_id": "...",
            "sections_text": "...",
            "part_index": 0
        }
    }
    """
    try:
        # Parse EventBridge event
        detail = json.loads(event.get('detail', '{}')) if isinstance(event.get('detail'), str) else event.get('detail', {})
        course_id = detail.get('course_id')
        sections_text = detail.get('sections_text')
        part_index = detail.get('part_index', 0)
        
        if not course_id:
            logger.error("Missing course_id in event")
            return {'statusCode': 400, 'body': json.dumps({'error': 'Missing course_id'})}
        
        if not sections_text:
            logger.error("Missing sections_text in event")
            return {'statusCode': 400, 'body': json.dumps({'error': 'Missing sections_text'})}
        
        # Load state from DynamoDB
        state = load_course_state(course_id)
        if not state:
            logger.error(f"Course state not found: {course_id}")
            publish_course_error_event(course_id, f"Course state not found: {course_id}")
            return {'statusCode': 404, 'body': json.dumps({'error': 'Course state not found'})}
        
        # Create event
        course_event = PartSectionsGeneratedEvent(sections_text=sections_text, part_index=part_index)
        
        # Process through logic layer
        result = reduce_course_event(state, course_event)
        
        # Check if we need to continue with next part or complete
        next_part_index = result.new_state.current_part_index or 0
        parts_list = result.new_state.parts_list or []
        all_parts_done = next_part_index >= len(parts_list)
        
        # Execute commands if any (LLMCommand for next part)
        sections_text_next = None
        for command in result.commands:
            command_result = execute_command(command, result.new_state)
            
            if isinstance(command, LLMCommand):
                if command_result.get('status') == 'success':
                    sections_text_next = command_result.get('content', '')
                else:
                    error_msg = command_result.get('error', 'Unknown error')
                    logger.error(f"Sections generation failed: {error_msg}")
                    publish_course_error_event(course_id, f"Sections generation failed: {error_msg}")
                    return {'statusCode': 500, 'body': json.dumps({'error': error_msg})}
        
        # Save updated state
        save_course_state(course_id, result.new_state)
        
        # Publish next event
        if all_parts_done:
            # All parts complete - publish AllPartsCompleteEvent
            publish_all_parts_complete_event(course_id)
            logger.info(f"All parts complete for course {course_id}")
        elif sections_text_next:
            # Continue with next part
            publish_part_sections_generated_event(course_id, sections_text_next, next_part_index)
            logger.info(f"Continuing with part {next_part_index} for course {course_id}")
        
        return {'statusCode': 200, 'body': json.dumps({
            'status': 'success',
            'all_parts_done': all_parts_done,
            'next_part_index': next_part_index if not all_parts_done else None
        })}
        
    except Exception as e:
        logger.error(f"Error in sections handler: {e}", exc_info=True)
        course_id = json.loads(event.get('detail', '{}')).get('course_id') if isinstance(event.get('detail'), str) else event.get('detail', {}).get('course_id')
        if course_id:
            publish_course_error_event(course_id, f"Sections handler error: {str(e)}")
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}
