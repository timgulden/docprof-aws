"""
Session handler Lambda - provides REST API for chat session management.
Adapts MAExpert session manager to AWS Lambda.

Endpoints:
- GET /chat/sessions - List all sessions
- POST /chat/sessions - Create new session
- GET /chat/sessions/{sessionId} - Get session details
- PATCH /chat/sessions/{sessionId} - Update session
- DELETE /chat/sessions/{sessionId} - Delete session
"""

import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

# Import shared utilities
from shared.session_manager import (
    list_sessions,
    create_session,
    get_session,
    update_session,
    delete_session
)
from shared.response import success_response, error_response
from shared.book_filter import update_selected_book_ids

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for session management endpoints.

    Routes based on HTTP method and path.
    """
    try:
        http_method = event.get('httpMethod', event.get('requestContext', {}).get('httpMethod', ''))
        path = event.get('path', event.get('requestContext', {}).get('resourcePath', ''))
        path_parameters = event.get('pathParameters', {})

        logger.info(f"Session handler: {http_method} {path}")

        # Route based on method and path
        if http_method == 'GET' and path == '/chat/sessions':
            return list_sessions_handler()
        elif http_method == 'POST' and path == '/chat/sessions':
            return create_session_handler(event)
        elif http_method == 'GET' and path == '/chat/sessions/{sessionId}':
            session_id = path_parameters.get('sessionId')
            return get_session_handler(session_id, event)
        elif http_method == 'PATCH' and path == '/chat/sessions/{sessionId}':
            session_id = path_parameters.get('sessionId')
            return update_session_handler(session_id, event)
        elif http_method == 'DELETE' and path == '/chat/sessions/{sessionId}':
            session_id = path_parameters.get('sessionId')
            return delete_session_handler(session_id)
        else:
            return error_response(f"Unsupported method/path: {http_method} {path}", 404)

    except Exception as e:
        logger.exception("Error in session handler")
        return error_response(f"Internal server error: {str(e)}", 500)


def list_sessions_handler() -> Dict[str, Any]:
    """Handle GET /chat/sessions - List all sessions."""
    try:
        sessions = list_sessions()

        # Convert datetime objects to ISO strings for JSON serialization
        response_sessions = []
        for session in sessions:
            session_copy = session.copy()
            if 'created_at' in session_copy and isinstance(session_copy['created_at'], datetime):
                session_copy['created_at'] = session_copy['created_at'].isoformat()
            if 'updated_at' in session_copy and isinstance(session_copy['updated_at'], datetime):
                session_copy['updated_at'] = session_copy['updated_at'].isoformat()
            response_sessions.append(session_copy)

        return success_response(response_sessions)
    except Exception as e:
        logger.exception("Error listing sessions")
        return error_response(f"Failed to list sessions: {str(e)}", 500)


def create_session_handler(event: Dict[str, Any]) -> Dict[str, Any]:
    """Handle POST /chat/sessions - Create new session."""
    try:
        # Parse request body
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})

        session_name = body.get('session_name')
        session_type = body.get('session_type', 'chat')
        session_context = body.get('session_context')
        selected_book_ids = body.get('selected_book_ids')  # Optional list of selected book IDs

        session = create_session(
            session_name=session_name,
            session_type=session_type,
            session_context=session_context,
            selected_book_ids=selected_book_ids
        )

        # Convert datetime objects to ISO strings
        response_session = session.copy()
        if 'created_at' in response_session and isinstance(response_session['created_at'], datetime):
            response_session['created_at'] = response_session['created_at'].isoformat()
        if 'updated_at' in response_session and isinstance(response_session['updated_at'], datetime):
            response_session['updated_at'] = response_session['updated_at'].isoformat()

        return success_response(response_session)
    except Exception as e:
        logger.exception("Error creating session")
        return error_response(f"Failed to create session: {str(e)}", 500)


def get_session_handler(session_id: str, event: Dict[str, Any]) -> Dict[str, Any]:
    """Handle GET /chat/sessions/{sessionId} - Get session details."""
    try:
        if not session_id:
            return error_response("Missing session_id", 400)

        session = get_session(session_id)
        if not session:
            return error_response(f"Session not found: {session_id}", 404)

        # Check if include_messages query parameter is set
        query_params = event.get('queryStringParameters', {})
        include_messages = query_params.get('include_messages', 'false').lower() == 'true'

        response_session = session.copy()

        # Convert datetime objects to ISO strings
        if 'created_at' in response_session and isinstance(response_session['created_at'], datetime):
            response_session['created_at'] = response_session['created_at'].isoformat()
        if 'updated_at' in response_session and isinstance(response_session['updated_at'], datetime):
            response_session['updated_at'] = response_session['updated_at'].isoformat()

        # If not including messages, remove them from response
        if not include_messages:
            response_session.pop('messages', None)

        return success_response(response_session)
    except Exception as e:
        logger.exception(f"Error getting session {session_id}")
        return error_response(f"Failed to get session: {str(e)}", 500)


def update_session_handler(session_id: str, event: Dict[str, Any]) -> Dict[str, Any]:
    """Handle PATCH /chat/sessions/{sessionId} - Update session."""
    try:
        if not session_id:
            return error_response("Missing session_id", 400)

        # Get existing session
        existing_session = get_session(session_id)
        if not existing_session:
            return error_response(f"Session not found: {session_id}", 404)

        # Parse request body
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})

        # Update fields
        updated_session = existing_session.copy()

        if 'session_name' in body:
            updated_session['session_name'] = body['session_name']
        if 'session_context' in body:
            updated_session['session_context'] = body['session_context']
        if 'selected_book_ids' in body:
            # Update selected book IDs using helper function
            updated_session = update_selected_book_ids(updated_session, body['selected_book_ids'])

        # Save updated session
        update_session(updated_session)

        # Convert datetime objects to ISO strings for response
        response_session = updated_session.copy()
        if 'created_at' in response_session and isinstance(response_session['created_at'], datetime):
            response_session['created_at'] = response_session['created_at'].isoformat()
        if 'updated_at' in response_session and isinstance(response_session['updated_at'], datetime):
            response_session['updated_at'] = response_session['updated_at'].isoformat()

        return success_response(response_session)
    except Exception as e:
        logger.exception(f"Error updating session {session_id}")
        return error_response(f"Failed to update session: {str(e)}", 500)


def delete_session_handler(session_id: str) -> Dict[str, Any]:
    """Handle DELETE /chat/sessions/{sessionId} - Delete session."""
    try:
        if not session_id:
            return error_response("Missing session_id", 400)

        # Check if session exists
        existing_session = get_session(session_id)
        if not existing_session:
            return error_response(f"Session not found: {session_id}", 404)

        # Delete session
        delete_session(session_id)

        return success_response({"message": "Session deleted successfully"})
    except Exception as e:
        logger.exception(f"Error deleting session {session_id}")
        return error_response(f"Failed to delete session: {str(e)}", 500)