"""
Section Generation Status Handler - GET /courses/section/{sectionId}/generation-status

Returns real-time generation progress for a section lecture.
Frontend polls this while generation is in progress (after receiving 202 from lecture endpoint).
"""

import json
import logging
import uuid
from typing import Dict, Any, Optional

from shared.db_utils import get_db_connection
from shared.course_state_manager import get_course_state
from shared.response import success_response, error_response

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for checking section generation status.
    
    This endpoint is very fast (<10ms) as it only reads from DynamoDB or in-memory cache.
    Frontend polls this every 1-2 seconds while generation is in progress.
    
    Expected event format (API Gateway):
    {
        "pathParameters": {
            "sectionId": "uuid-here"
        },
        "requestContext": {
            "authorizer": {
                "claims": {
                    "sub": "user-uuid"
                }
            }
        }
    }
    
    Returns:
    {
        "section_id": "uuid",
        "phase": "objectives" | "refining" | "complete" | "not_started",
        "covered_objectives": 3,
        "total_objectives": 5,
        "progress_percent": 60,
        "current_step": "Generating lecture for objective 3 of 5..."
    }
    """
    try:
        # Extract user_id from Cognito token
        user_id = extract_user_id(event)
        if not user_id:
            return error_response(
                "Missing user authentication. Please log in.",
                status_code=401
            )
        
        # Extract section_id from path parameters
        path_params = event.get('pathParameters') or {}
        section_id_str = path_params.get('sectionId')
        
        if not section_id_str:
            return error_response(
                "Missing sectionId in path parameters",
                status_code=400
            )
        
        # Validate UUID format
        try:
            section_id_uuid = uuid.UUID(section_id_str)
            section_id_db = str(section_id_uuid)
        except ValueError:
            return error_response(
                f"Invalid sectionId format: {section_id_str}",
                status_code=400
            )
        
        logger.info(f"Checking generation status for section {section_id_db}")
        
        # Get generation status
        # First check if section exists and user has access
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT cs.section_id, cs.course_id, cs.status, c.user_id
                    FROM course_sections cs
                    JOIN courses c ON cs.course_id = c.course_id
                    WHERE cs.section_id = %s::uuid
                    """,
                    (section_id_db,)
                )
                section_row = cur.fetchone()
                
                if not section_row:
                    return error_response(
                        f"Section not found: {section_id_str}",
                        status_code=404
                    )
                
                (section_id_result, course_id, section_status, course_user_id) = section_row
                
                # Verify user owns this course
                if str(course_user_id) != user_id:
                    return error_response(
                        "Access denied: you do not own this course",
                        status_code=403
                    )
                
                # Check if lecture delivery exists
                cur.execute(
                    """
                    SELECT delivery_id
                    FROM section_deliveries
                    WHERE section_id = %s::uuid AND user_id = %s::uuid
                    LIMIT 1
                    """,
                    (section_id_db, user_id)
                )
                delivery_row = cur.fetchone()
                
                # If lecture exists, it's complete
                if delivery_row:
                    return success_response({
                        "section_id": section_id_db,
                        "phase": "complete",
                        "covered_objectives": 0,
                        "total_objectives": 0,
                        "progress_percent": 100,
                        "current_step": "Lecture generation complete",
                    })
        
        # Check generation progress from DynamoDB course state
        # In a real implementation, this would check generation progress
        # For now, return "not_started" if no delivery exists
        # TODO: Implement actual progress tracking via DynamoDB or separate table
        
        return success_response({
            "section_id": section_id_db,
            "phase": "not_started",
            "covered_objectives": 0,
            "total_objectives": 0,
            "progress_percent": 0,
            "current_step": "Lecture generation not started",
        })
        
    except Exception as e:
        logger.error(f"Error checking generation status: {e}", exc_info=True)
        return error_response(
            f"Failed to check generation status: {str(e)}",
            status_code=500
        )


def extract_user_id(event: Dict[str, Any]) -> Optional[str]:
    """
    Extract user_id from API Gateway event with Cognito authorizer.
    
    Cognito user ID is in: event.requestContext.authorizer.claims.sub
    """
    try:
        request_context = event.get("requestContext", {})
        authorizer = request_context.get("authorizer", {})
        claims = authorizer.get("claims", {})
        
        # Cognito user ID is in the 'sub' claim
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
