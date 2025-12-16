"""
Course Request Handler - Entry point for course generation.

Asynchronous handler that initiates course generation via EventBridge.
Returns immediately with course_id and status, allowing UI to poll for progress.
"""

import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from uuid import uuid4

# Import course logic and models
from shared.logic.courses import (
    create_initial_course_state,
    reduce_course_event,
)
from shared.core.course_models import CoursePreferences, CourseState
from shared.core.course_events import CourseRequestedEvent
from shared.core.commands import EmbedCommand
from shared.command_executor import execute_command
from shared.course_state_manager import save_course_state
from shared.event_publisher import publish_course_requested_event, publish_embedding_generated_event
from shared.response import success_response, error_response
from shared.db_utils import get_db_connection

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for course generation requests.
    
    Asynchronous flow:
    1. Create initial course state
    2. Process CourseRequestedEvent to get first command (EmbedCommand)
    3. Execute EmbedCommand immediately (fast operation)
    4. Save state to DynamoDB
    5. Publish EmbeddingGeneratedEvent to EventBridge (triggers async pipeline)
    6. Return immediately with course_id and status
    
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
        # Support both 'hours' and 'time_hours' for compatibility
        hours = body.get('hours') or body.get('time_hours', 2.0)
        preferences_dict = body.get('preferences', {})
        
        if not query:
            return error_response("Missing required field: query", status_code=400)
        
        # Convert preferences dict to CoursePreferences model
        preferences = CoursePreferences(**preferences_dict) if preferences_dict else CoursePreferences()
        
        # Create initial course state
        course_state = create_initial_course_state()
        course_id = str(uuid4())  # Generate course ID (session_id)
        course_state.session_id = course_id
        
        # Create course request event
        course_event = CourseRequestedEvent(
            query=query,
            time_hours=float(hours),
            preferences=preferences
        )
        
        # Process course request through logic layer to get first command
        current_result = reduce_course_event(course_state, course_event)
        current_state = current_result.new_state
        
        # Execute first command (should be EmbedCommand) synchronously
        # This is fast and allows us to publish EmbeddingGeneratedEvent immediately
        if current_result.commands and isinstance(current_result.commands[0], EmbedCommand):
            command = current_result.commands[0]
            logger.info(f"Executing initial command: {command.command_name}")
            command_result = execute_command(command, state=current_state)
            
            if command_result.get('status') == 'success' and 'embedding' in command_result:
                embedding = command_result['embedding']
                logger.info(f"Generated embedding (length: {len(embedding)})")
                
                # Update state with embedding event
                from shared.core.course_events import EmbeddingGeneratedEvent
                embedding_event = EmbeddingGeneratedEvent(embedding=embedding)
                current_result = reduce_course_event(current_state, embedding_event)
                current_state = current_result.new_state
                
                # Save state to DynamoDB
                save_course_state(course_id, current_state)
                logger.info(f"Saved initial course state: {course_id}")
                
                # Save basic course record to PostgreSQL immediately so outline endpoint works
                # Extract user_id from event (Cognito token)
                user_id = extract_user_id(event)
                if user_id:
                    save_initial_course_record(course_id, user_id, query, hours, preferences_dict)
                    logger.info(f"Saved initial course record to PostgreSQL: {course_id}")
                
                # Publish EmbeddingGeneratedEvent to EventBridge to continue async pipeline
                publish_embedding_generated_event(course_id, embedding)
                logger.info(f"Published EmbeddingGeneratedEvent for course: {course_id}")
                
                # Return immediately with course_id and status
                # Frontend expects camelCase: courseId, title, message
                return success_response({
                    'courseId': course_id,  # camelCase for frontend
                    'course_id': course_id,  # Also include snake_case for backward compatibility
                    'title': query[:100] if len(query) > 100 else query,  # Temporary title from query
                    'message': f'Course generation started. Poll /course-status/{course_id} for progress.',
                    'status': 'processing',
                    'pending': True,
                    'query': query,
                    'hours': hours,
                })
            else:
                error_msg = command_result.get('error', 'Failed to generate embedding')
                logger.error(f"Embedding generation failed: {error_msg}")
                return error_response(f"Failed to start course generation: {error_msg}", status_code=500)
        else:
            # Unexpected: no EmbedCommand or different command type
            logger.warning(f"Unexpected first command: {current_result.commands[0].command_name if current_result.commands else 'None'}")
            # Still save state and publish CourseRequestedEvent as fallback
            save_course_state(course_id, current_state)
            
            # Save basic course record to PostgreSQL immediately
            user_id = extract_user_id(event)
            if user_id:
                save_initial_course_record(course_id, user_id, query, hours, preferences_dict)
                logger.info(f"Saved initial course record to PostgreSQL (fallback): {course_id}")
            
            publish_course_requested_event(course_id, query, float(hours), preferences_dict)
            return success_response({
                'courseId': course_id,  # camelCase for frontend
                'course_id': course_id,  # Also include snake_case for backward compatibility
                'title': query[:100] if len(query) > 100 else query,  # Temporary title from query
                'message': 'Course generation started. Poll /courses/{course_id}/status for progress.',
                'status': 'processing',
                'pending': True,
                'query': query,
                'hours': hours,
            })
        
    except Exception as e:
        logger.error(f"Error in course request handler: {e}", exc_info=True)
        return error_response(f"Internal server error: {str(e)}", status_code=500)


def extract_user_id(event: Dict[str, Any]) -> Optional[str]:
    """Extract user_id from API Gateway event with Cognito authorizer."""
    try:
        request_context = event.get("requestContext", {})
        authorizer = request_context.get("authorizer", {})
        claims = authorizer.get("claims", {})
        user_id = claims.get("sub")
        if user_id:
            logger.info(f"Extracted user_id from Cognito token: {user_id}")
            return user_id
        else:
            logger.warning("No user_id found in Cognito claims")
            return None
    except Exception as e:
        logger.error(f"Error extracting user_id: {e}", exc_info=True)
        return None


def save_initial_course_record(course_id: str, user_id: str, query: str, hours: float, preferences_dict: Dict[str, Any]) -> None:
    """Save initial course record to PostgreSQL so outline endpoint works immediately."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Insert course with initial status
                cur.execute(
                    """
                    INSERT INTO courses (
                        course_id, user_id, title, original_query,
                        estimated_hours, status, preferences, created_at, last_modified
                    ) VALUES (
                        %s::uuid, %s::uuid, %s, %s, %s, %s, %s::jsonb, NOW(), NOW()
                    )
                    ON CONFLICT (course_id) DO NOTHING
                    """,
                    (
                        course_id,
                        user_id,
                        query[:200] if len(query) > 200 else query,  # Title from query
                        query,
                        float(hours),
                        'active',  # Initial status (valid: 'active', 'completed', 'archived')
                        json.dumps(preferences_dict) if preferences_dict else '{}',
                    )
                )
                conn.commit()
                logger.info(f"Saved initial course record: {course_id}")
    except Exception as e:
        logger.error(f"Failed to save initial course record: {e}", exc_info=True)
        # Don't fail the request if this fails - course will be saved later in workflow
