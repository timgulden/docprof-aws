"""
Course Standalone Section Lambda - finds best section for available time.
Follows MAExpert's select_standalone_section logic.
"""

import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Get best standalone section that fits available time.
    
    Path: POST /courses/{courseId}/standalone
    Body: {"available_minutes": 15}
    Auth: Requires Cognito user_id
    
    Returns:
    - section_id: ID of best matching section
    - section_title: Title of the section
    - estimated_minutes: Section duration
    - null if no suitable section found
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
        
        # Parse request body for available_minutes
        body = {}
        if event.get('body'):
            try:
                body = json.loads(event['body'])
            except json.JSONDecodeError:
                return error_response(400, "Invalid JSON in request body")
        
        available_minutes = body.get('available_minutes', 20)  # Default 20 minutes
        
        logger.info(f"Finding standalone section for course {course_id}, {available_minutes} minutes available")
        
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
                
                # Find best standalone section that fits time constraint
                # Prioritize: incomplete, can_standalone=true, fits in available time
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
                      AND can_standalone = true
                      AND estimated_minutes <= %s
                    ORDER BY 
                        ABS(estimated_minutes - %s) ASC,  -- Closest to available time
                        order_index ASC                    -- Earlier sections preferred
                    LIMIT 1
                """, (course_id, available_minutes, available_minutes))
                
                section = cur.fetchone()
                
                if not section:
                    logger.info(f"No suitable standalone section found for {available_minutes} minutes")
                    return success_response({
                        "section_id": None,
                        "message": f"No standalone section found that fits in {available_minutes} minutes"
                    })
                
                section_id, title, order_index, estimated_minutes_actual, can_standalone = section
                
                logger.info(f"Found standalone section: {title} ({estimated_minutes_actual} min)")
                
                return success_response({
                    "section_id": str(section_id),
                    "section_title": title,
                    "order_index": order_index,
                    "estimated_minutes": estimated_minutes_actual,
                    "can_standalone": can_standalone,
                })
        
    except Exception as e:
        logger.error(f"Error getting standalone section: {e}", exc_info=True)
        return error_response(500, f"Failed to get standalone section: {str(e)}")
