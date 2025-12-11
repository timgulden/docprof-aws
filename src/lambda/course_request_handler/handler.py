"""
Course Request Handler - Entry point for course generation.

Receives course generation requests and initiates the event-driven workflow.
This is Phase 0 - it creates the initial state and publishes the first event.
"""

import json
import logging
from typing import Dict, Any
from uuid import uuid4

from shared.logic.courses import create_initial_course_state, reduce_course_event
from shared.core.course_models import CoursePreferences
from shared.core.course_events import CourseRequestedEvent
from shared.command_executor import execute_command
from shared.course_state_manager import save_course_state
from shared.event_publisher import publish_course_requested_event
from shared.response import success_response, error_response

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for course generation requests.
    
    Expected event format (API Gateway):
    {
        "body": "{\"query\": \"Learn DCF valuation\", \"hours\": 2.0, \"preferences\": {...}}",
        "httpMethod": "POST",
        "path": "/courses",
        "headers": {...}
    }
    """
    try:
        # Parse request body
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})
        
        query = body.get('query')
        hours = body.get('hours', 2.0)
        preferences_dict = body.get('preferences', {})
        
        if not query:
            return error_response("Missing required field: query", status_code=400)
        
        # Generate course_id (session_id)
        course_id = str(uuid4())
        
        # Convert preferences dict to CoursePreferences model
        preferences = CoursePreferences(**preferences_dict) if preferences_dict else CoursePreferences()
        
        # Create initial course state
        course_state = create_initial_course_state()
        course_state.session_id = course_id
        
        # Create course request event
        course_event = CourseRequestedEvent(
            query=query,
            time_hours=float(hours),
            preferences=preferences
        )
        
        # Process course request through logic layer
        result = reduce_course_event(course_state, course_event)
        
        # Save initial state to DynamoDB
        save_course_state(course_id, result.new_state)
        
        # Execute first command (EmbedCommand)
        from shared.core.commands import EmbedCommand
        
        commands_executed = []
        for command in result.commands:
            command_result = execute_command(command, result.new_state)
            commands_executed.append({
                'command_type': type(command).__name__,
                'result': command_result
            })
            
            # If EmbedCommand succeeded, publish EmbeddingGeneratedEvent
            if isinstance(command, EmbedCommand) and command_result.get('status') == 'success':
                if 'embedding' in command_result:
                    from shared.event_publisher import publish_embedding_generated_event
                    publish_embedding_generated_event(
                        course_id=course_id,
                        embedding=command_result['embedding'],
                        task=command.task
                    )
        
        # Return response with course_id for polling
        return success_response({
            'course_id': course_id,
            'ui_message': result.ui_message,
            'status': 'generating',
            'phase': 'embedding',
        })
        
    except Exception as e:
        logger.error(f"Error in course request handler: {e}", exc_info=True)
        return error_response(f"Internal server error: {str(e)}", status_code=500)
