"""
Course Next Section Lambda - returns next incomplete section in course.
Follows MAExpert's select_next_section logic.
"""

import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Get next incomplete section for a course.
    
    Path: POST /courses/{courseId}/next
    Auth: Requires Cognito user_id
    
    Returns:
    - section_id: ID of next section to complete
    - section_title: Title of the section
    - order_index: Position in course
    - null if course is complete
    """
    try:
        from shared.db_utils import get_db_connection
        from shared.response import success_response, error_response
        
        # Extract user_id from Cognito
        user_id = event.get('requestContext', {}).get('authorizer', {}).get('claims', {}).get('sub')
        if not user_id:
            return error_response(401, "Unauthorized - missing user_id")
        
        # Extract course_id
        course_id = event.get('pathParameters', {}).get('courseId')
        if not course_id:
            return error_response(400, "Missing courseId")
        
        logger.info(f"Finding next section for course {course_id}, user {user_id}")
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Verify course belongs to user
                cur.execute("""
                    SELECT course_id, title FROM courses
                    WHERE course_id = %s AND user_id = %s
                """, (course_id, user_id))
                
                course = cur.fetchone()
                if not course:
                    return error_response(404, "Course not found or you don't have access")
                
                # Find next incomplete section (ordered by order_index)
                cur.execute("""
                    SELECT 
                        section_id,
                        title,
                        order_index,
                        estimated_minutes,
                        can_standalone
                    FROM course_sections
                    WHERE course_id = %s
                      AND status != 'completed'
                    ORDER BY order_index ASC
                    LIMIT 1
                """, (course_id,))
                
                next_section = cur.fetchone()
                
                if not next_section:
                    logger.info(f"No incomplete sections - course {course_id} is complete")
                    return success_response({
                        "section_id": None,
                        "message": "Course complete - all sections finished!"
                    })
                
                section_id, title, order_index, estimated_minutes, can_standalone = next_section
                
                logger.info(f"Next section: {title} (ID: {section_id}, order: {order_index})")
                
                return success_response({
                    "section_id": str(section_id),
                    "section_title": title,
                    "order_index": order_index,
                    "estimated_minutes": estimated_minutes,
                    "can_standalone": can_standalone,
                })
        
    except Exception as e:
        logger.error(f"Error getting next section: {e}", exc_info=True)
        return error_response(500, f"Failed to get next section: {str(e)}")
