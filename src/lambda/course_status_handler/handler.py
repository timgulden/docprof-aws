"""
Course Status Handler - Returns current status of course generation.

Reads course state from DynamoDB and verifies sections in PostgreSQL.
Used by UI for polling course generation progress.
"""

import json
import logging
from typing import Dict, Any, Optional

from shared.course_state_manager import load_course_state
from shared.db_utils import get_db_connection
from shared.response import success_response, error_response

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for course status requests.
    
    IMPORTANT: Only reports "complete" when sections are actually stored in DB.
    This prevents the frontend from navigating to an empty course.
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
        
        # Try to load state from DynamoDB
        state = load_course_state(course_id)
        
        # FALLBACK: If DynamoDB state doesn't exist, check PostgreSQL directly
        if not state:
            logger.warning(f"No DynamoDB state for {course_id}, checking PostgreSQL...")
            return _get_status_from_postgres(course_id)
        
        # Determine progress phase based on actual CourseState fields
        phase = "initializing"
        status = "processing"
        progress = {}
        error_message = None
        
        # Check for errors (if error_message exists in state)
        if hasattr(state, 'error_message') and state.error_message:
            status = "error"
            error_message = state.error_message
        
        if state.pending_course_query:
            phase = "searching_books"
            progress['message'] = "Searching knowledge base for relevant content..."
        
        # Check if parts have been generated (parts_list is populated)
        if state.parts_list and len(state.parts_list) > 0:
            phase = "generating_sections"
            progress['parts_count'] = len(state.parts_list)
            progress['current_part_index'] = state.current_part_index or 0
            progress['total_parts'] = len(state.parts_list)
            progress['message'] = f"Generating sections for part {(state.current_part_index or 0) + 1} of {len(state.parts_list)}..."
            
            # Check if outline text is being built
            if state.outline_text and len(state.outline_text) > 0:
                progress['outline_length'] = len(state.outline_text)
        
        # Check if all parts are complete
        if state.outline_complete:
            phase = "reviewing_outline"
            progress['outline_complete'] = True
            progress['message'] = "Reviewing and finalizing course outline..."
        
        # CRITICAL: Only mark as complete if sections ACTUALLY exist in database
        if state.current_course and state.current_course.course_id:
            # Verify sections exist in PostgreSQL
            section_count = _get_section_count(course_id)
            
            if section_count > 0:
                # Sections are stored - truly complete!
                phase = "complete"
                status = "complete"
                progress['course_id'] = state.current_course.course_id
                progress['title'] = state.current_course.title
                progress['section_count'] = section_count
                progress['message'] = f"Course created with {section_count} sections!"
                logger.info(f"Course {course_id} is complete with {section_count} sections")
            else:
                # Course record exists but sections not yet stored
                phase = "storing_sections"
                progress['message'] = "Storing course sections..."
                logger.info(f"Course {course_id} has record but 0 sections - still storing")
        
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


def _get_section_count(course_id: str) -> int:
    """Check how many sections exist for this course in PostgreSQL."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM course_sections WHERE course_id = %s::uuid",
                    (course_id,)
                )
                result = cur.fetchone()
                return result[0] if result else 0
    except Exception as e:
        logger.warning(f"Could not check section count for {course_id}: {e}")
        return 0


def _get_status_from_postgres(course_id: str):
    """Fallback: Get course status from PostgreSQL when DynamoDB state unavailable."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Check if course exists
                cur.execute(
                    "SELECT course_id, title, estimated_hours, original_query FROM courses WHERE course_id = %s::uuid",
                    (course_id,)
                )
                course = cur.fetchone()
                
                if not course:
                    return error_response(f"Course not found: {course_id}", status_code=404)
                
                # Count sections
                cur.execute(
                    "SELECT COUNT(*) FROM course_sections WHERE course_id = %s::uuid",
                    (course_id,)
                )
                section_count = cur.fetchone()[0]
                
                # Determine phase based on section count
                if section_count > 0:
                    phase = "complete"
                    status = "complete"
                    message = f"Course created with {section_count} sections!"
                else:
                    phase = "generating_sections"
                    status = "processing"
                    message = "Generating course sections..."
                
                return success_response({
                    'course_id': course_id,
                    'status': status,
                    'phase': phase,
                    'progress': {
                        'course_id': course_id,
                        'title': course[1],  # title
                        'section_count': section_count,
                        'message': message,
                    },
                    'query': course[3],  # original_query
                    'hours': float(course[2]) if course[2] else None,  # estimated_hours
                })
    except Exception as e:
        logger.error(f"Error getting status from PostgreSQL for {course_id}: {e}", exc_info=True)
        return error_response(f"Internal server error: {str(e)}", status_code=500)
