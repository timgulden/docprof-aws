"""
Section Complete Handler - POST /courses/section/{sectionId}/complete

Marks a section as completed by the user.
Used when user finishes watching/listening to a section lecture.
"""

import json
import logging
import uuid
from typing import Dict, Any, Optional
from datetime import datetime

from shared.db_utils import get_db_connection
from shared.response import success_response, error_response

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for marking section as complete.
    
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
        "message": "Section marked as complete",
        "section_id": "uuid",
        "completed_at": "2025-01-XX..."
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
        
        logger.info(f"Marking section {section_id_db} as complete for user {user_id}")
        
        # Update section status in database
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # First verify the section exists and user has access
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
                
                (section_id_result, course_id, current_status, course_user_id) = section_row
                
                # Verify user owns this course
                if str(course_user_id) != user_id:
                    return error_response(
                        "Access denied: you do not own this course",
                        status_code=403
                    )
                
                # Update section status to 'completed'
                completed_at = datetime.utcnow()
                cur.execute(
                    """
                    UPDATE course_sections
                    SET status = 'completed',
                        completed_at = %s
                    WHERE section_id = %s::uuid
                    RETURNING section_id, status, completed_at
                    """,
                    (completed_at, section_id_db)
                )
                updated_row = cur.fetchone()
                
                if not updated_row:
                    return error_response(
                        f"Failed to update section status",
                        status_code=500
                    )
                
                conn.commit()
                
                (updated_section_id, updated_status, updated_completed_at) = updated_row
                
                logger.info(f"Section {section_id_db} marked as {updated_status}")
                
                return success_response({
                    "message": "Section marked as complete",
                    "section_id": str(updated_section_id),
                    "status": updated_status,
                    "completed_at": updated_completed_at.isoformat() if updated_completed_at else None,
                })
        
    except Exception as e:
        logger.error(f"Error marking section as complete: {e}", exc_info=True)
        return error_response(
            f"Failed to mark section as complete: {str(e)}",
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
