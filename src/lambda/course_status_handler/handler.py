"""
Course Status Handler - Returns current status of course generation.

Reads course state from DynamoDB and returns status, progress, and any errors.
Used by UI for polling course generation progress.
"""

import json
import logging
from typing import Dict, Any, Optional

from shared.course_state_manager import load_course_state
from shared.response import success_response, error_response

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for course status requests.
    
    Expected event format (API Gateway):
    {
        "pathParameters": {"courseId": "uuid-here"},
        "httpMethod": "GET",
        "path": "/courses/{courseId}/status",
        "headers": {...}
    }
    """
    try:
        # Extract course_id from path parameters or query string
        course_id = None
        
        if event.get('pathParameters') and event['pathParameters'].get('courseId'):
            course_id = event['pathParameters']['courseId']
        elif event.get('queryStringParameters') and event['queryStringParameters'].get('courseId'):
            course_id = event['queryStringParameters']['courseId']
        
        if not course_id:
            return error_response("Missing required parameter: courseId", status_code=400)
        
        # Load state from DynamoDB
        state = load_course_state(course_id)
        
        if not state:
            return error_response(f"Course not found: {course_id}", status_code=404)
        
        # Determine status based on state
        status = "processing"
        progress = {}
        error_message = None
        
        # Check if course is complete (stored in database)
        if state.current_course and state.current_course.course_id:
            status = "complete"
            progress['course_id'] = state.current_course.course_id
            progress['title'] = state.current_course.title
            progress['estimated_hours'] = state.current_course.estimated_hours
        
        # Check for errors (if error_message exists in state)
        if hasattr(state, 'error_message') and state.error_message:
            status = "error"
            error_message = state.error_message
        
        # Determine progress phase based on actual CourseState fields
        phase = "initializing"
        progress = {}
        
        if state.pending_course_query:
            phase = "searching_books"
        
        # Check if parts have been generated (parts_list is populated)
        if state.parts_list and len(state.parts_list) > 0:
            phase = "generating_sections"
            progress['parts_count'] = len(state.parts_list)
            progress['current_part_index'] = state.current_part_index
            progress['total_parts'] = len(state.parts_list)
            
            # Check if outline text is being built
            if state.outline_text and len(state.outline_text) > 0:
                progress['outline_length'] = len(state.outline_text)
        
        # Check if all parts are complete
        if state.outline_complete:
            phase = "reviewing_outline"
            progress['outline_complete'] = True
        
        # Check if course has been stored (has current_course with course_id)
        if state.current_course and state.current_course.course_id:
            phase = "complete"
            progress['course_id'] = state.current_course.course_id
            progress['title'] = state.current_course.title
        
        # Build response
        response_data = {
            'course_id': course_id,
            'status': status,
            'phase': phase,
            'progress': progress,
            'query': state.pending_course_query if state.pending_course_query else None,
            'hours': float(state.pending_course_hours) if state.pending_course_hours else None,
        }
        
        if error_message:
            response_data['error'] = error_message
        
        # Include UI message if available
        if hasattr(state, 'ui_message') and state.ui_message:
            response_data['message'] = state.ui_message
        
        return success_response(response_data)
        
    except Exception as e:
        logger.error(f"Error in course status handler: {e}", exc_info=True)
        return error_response(f"Internal server error: {str(e)}", status_code=500)
