"""
Course Outline Reviewer Handler - Phase 5: Handle outline review.

Receives AllPartsCompleteEvent from EventBridge.
Checks if outline needs review (time variance > 5%).
If needed, reviews and adjusts outline, publishes OutlineReviewEvent.
If not needed, directly stores course.
"""

import json
import logging
from typing import Dict, Any

from shared.logic.courses import reduce_course_event
from shared.core.course_events import AllPartsCompleteEvent
from shared.command_executor import execute_command
from shared.course_state_manager import load_course_state, save_course_state
from shared.event_publisher import (
    publish_outline_reviewed_event,
    publish_course_error_event
)
from shared.core.commands import LLMCommand

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for AllPartsCompleteEvent.
    
    Expected event format (EventBridge):
    {
        "source": "docprof.course",
        "detail-type": "AllPartsComplete",
        "detail": {
            "course_id": "..."
        }
    }
    """
    try:
        # Parse EventBridge event
        detail = json.loads(event.get('detail', '{}')) if isinstance(event.get('detail'), str) else event.get('detail', {})
        course_id = detail.get('course_id')
        
        if not course_id:
            logger.error("Missing course_id in event")
            return {'statusCode': 400, 'body': json.dumps({'error': 'Missing course_id'})}
        
        # Load state from DynamoDB
        state = load_course_state(course_id)
        if not state:
            logger.error(f"Course state not found: {course_id}")
            publish_course_error_event(course_id, f"Course state not found: {course_id}")
            return {'statusCode': 404, 'body': json.dumps({'error': 'Course state not found'})}
        
        # Create event and process through logic layer
        course_event = AllPartsCompleteEvent()
        logger.info(f"Outline reviewer: Processing AllPartsCompleteEvent for course {course_id}")
        logger.info(f"Outline reviewer: State has outline_text length: {len(state.outline_text or '')}")
        logger.info(f"Outline reviewer: State has parts_list: {len(state.parts_list or [])} parts")
        
        result = reduce_course_event(state, course_event)
        
        # Execute commands
        # Could be LLMCommand (if review needed) or CreateCourseCommand/CreateSectionsCommand (if no review)
        reviewed_outline_text = None
        needs_review = False
        
        from shared.core.commands import CreateCourseCommand, CreateSectionsCommand
        
        logger.info(f"Outline reviewer: Logic returned {len(result.commands)} commands")
        logger.info(f"Outline reviewer: Command types: {[type(c).__name__ for c in result.commands]}")
        
        if len(result.commands) == 0:
            logger.error(f"CRITICAL: No commands returned from reduce_course_event! This means course won't be stored.")
            publish_course_error_event(course_id, "No commands returned from outline review - course storage failed")
            return {'statusCode': 500, 'body': json.dumps({'error': 'No commands returned from logic layer'})}
        for idx, command in enumerate(result.commands):
            logger.info(f"Executing command {idx+1}/{len(result.commands)}: {type(command).__name__}")
            command_result = execute_command(command, result.new_state)
            logger.info(f"Command {idx+1} result: status={command_result.get('status')}, sections_count={command_result.get('sections_count', 'N/A')}")
            
            if isinstance(command, LLMCommand):
                needs_review = True
                if command_result.get('status') == 'success':
                    reviewed_outline_text = command_result.get('content', '')
                else:
                    error_msg = command_result.get('error', 'Unknown error')
                    logger.error(f"Outline review failed: {error_msg}")
                    publish_course_error_event(course_id, f"Outline review failed: {error_msg}")
                    return {'statusCode': 500, 'body': json.dumps({'error': error_msg})}
            
            elif isinstance(command, CreateCourseCommand):
                # Course storage
                stored_course_id = command_result.get('course_id')
                logger.info(f"CreateCourseCommand execution result: status={command_result.get('status')}, course_id={stored_course_id}")
                logger.info(f"CreateCourseCommand course title: '{command.course.title}'")
                
                if command_result.get('status') != 'success':
                    error_msg = command_result.get('error', 'Unknown error')
                    logger.error(f"CreateCourseCommand failed: {error_msg}")
                    publish_course_error_event(course_id, f"Course storage failed: {error_msg}")
                    return {'statusCode': 500, 'body': json.dumps({'error': error_msg})}
                else:
                    logger.info(f"CreateCourseCommand succeeded: course_id={stored_course_id}, title='{command.course.title}'")
            
            elif isinstance(command, CreateSectionsCommand):
                # Sections storage
                sections_count = command_result.get('sections_count', 0)
                logger.info(f"CreateSectionsCommand execution result: status={command_result.get('status')}, sections_count={sections_count}")
                
                if command_result.get('status') != 'success':
                    error_msg = command_result.get('error', 'Unknown error')
                    logger.error(f"CreateSectionsCommand failed: {error_msg}")
                    logger.error(f"CreateSectionsCommand command had {len(command.sections)} sections to store")
                    publish_course_error_event(course_id, f"Sections storage failed: {error_msg}")
                    return {'statusCode': 500, 'body': json.dumps({'error': error_msg})}
                else:
                    logger.info(f"CreateSectionsCommand succeeded: stored {sections_count} sections")
                    if sections_count == 0:
                        logger.error(f"CRITICAL: CreateSectionsCommand succeeded but stored 0 sections!")
                        logger.error(f"CRITICAL: Command had {len(command.sections)} sections in the command object")
                        # Don't fail here - let it continue, but log the issue
                    else:
                        logger.info(f"SUCCESS: {sections_count} sections stored in database for course {course_id}")
        
        # Save updated state
        save_course_state(course_id, result.new_state)
        
        # Publish appropriate event
        if needs_review and reviewed_outline_text:
            # Review was needed and completed - publish OutlineReviewEvent for storage handler
            publish_outline_reviewed_event(course_id, reviewed_outline_text)
            logger.info(f"Reviewed outline for course {course_id}")
        else:
            # No review needed - course already stored, publish CourseStoredEvent
            from shared.event_publisher import publish_course_stored_event
            publish_course_stored_event(course_id, course_id)
            logger.info(f"No review needed for course {course_id}, course stored")
        
        return {'statusCode': 200, 'body': json.dumps({
            'status': 'success',
            'review_needed': needs_review
        })}
        
    except Exception as e:
        logger.error(f"Error in outline reviewer handler: {e}", exc_info=True)
        course_id = json.loads(event.get('detail', '{}')).get('course_id') if isinstance(event.get('detail'), str) else event.get('detail', {}).get('course_id')
        if course_id:
            publish_course_error_event(course_id, f"Outline reviewer handler error: {str(e)}")
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}
