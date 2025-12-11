"""
Course generator Lambda - generates course outlines using multi-phase LLM approach.

Follows FP mapping strategy:
- Uses pure logic functions from shared/logic/courses.py
- Adapts effects to AWS services (Bedrock, Aurora, DynamoDB)
- Thin handler wrapper around logic layer

Course Generation Flow:
1. User requests course (query, hours, preferences)
2. Generate embedding for query
3. Search book summaries for relevant material
4. Phase 1: Generate course parts structure
5. Phase 2-N: Expand each part into sections
6. Phase N+1: Review and adjust for time accuracy
7. Store course outline in database
"""

import json
import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from uuid import uuid4

# Import shared utilities
from shared.bedrock_client import invoke_claude, generate_embeddings
from shared.db_utils import get_db_connection, vector_similarity_search
from shared.response import success_response, error_response

# Import course logic and models
from shared.logic.courses import (
    create_initial_course_state,
    reduce_course_event,
    request_course,
)
from shared.core.course_models import CoursePreferences, CourseState
from shared.core.course_events import CourseRequestedEvent
from shared.core.commands import LLMCommand, EmbedCommand, SearchBookSummariesCommand

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
        
        # Convert preferences dict to CoursePreferences model
        preferences = CoursePreferences(**preferences_dict) if preferences_dict else CoursePreferences()
        
        # Create initial course state
        course_state = create_initial_course_state()
        course_state.session_id = str(uuid4())  # Generate session ID for this course generation
        
        # Create course request event
        course_event = CourseRequestedEvent(
            query=query,
            time_hours=float(hours),
            preferences=preferences
        )
        
        # Process course request through logic layer
        result = reduce_course_event(course_state, course_event)
        
        # Execute commands (effects)
        # For now, we'll handle the first command (EmbedCommand)
        # In a full implementation, this would be a command executor pattern
        commands_executed = []
        for command in result.commands:
            if isinstance(command, EmbedCommand):
                # Generate embedding
                embedding = generate_embeddings(command.text)
                commands_executed.append({
                    'type': 'embedding_generated',
                    'embedding': embedding
                })
                # TODO: Continue pipeline with embedding
                # This would trigger the next step in the course generation flow
            elif isinstance(command, LLMCommand):
                # Call LLM with prompt
                if command.prompt_name:
                    # Use prompt registry (would need to import get_prompt)
                    # For now, return command info
                    commands_executed.append({
                        'type': 'llm_command',
                        'prompt_name': command.prompt_name,
                        'prompt_variables': command.prompt_variables
                    })
                else:
                    # Use inline prompt
                    response = invoke_claude(
                        messages=[{"role": "user", "content": command.prompt}],
                        max_tokens=command.max_tokens,
                        temperature=command.temperature,
                        stream=False
                    )
                    commands_executed.append({
                        'type': 'llm_response',
                        'content': response.get('content', '')
                    })
            elif isinstance(command, SearchBookSummariesCommand):
                # Search book summaries
                # TODO: Implement book summary search
                commands_executed.append({
                    'type': 'book_search',
                    'query_embedding': command.query_embedding[:5]  # Sample
                })
        
        # Return response
        return success_response({
            'session_id': course_state.session_id,
            'ui_message': result.ui_message,
            'commands_executed': len(commands_executed),
            'state': {
                'pending_course_query': result.new_state.pending_course_query,
                'pending_course_hours': result.new_state.pending_course_hours,
            }
        })
        
    except Exception as e:
        logger.error(f"Error in course generator: {e}", exc_info=True)
        return error_response(f"Internal server error: {str(e)}", status_code=500)
