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
                    SELECT cs.section_id, cs.course_id, cs.status, cs.generation_progress, 
                           cs.learning_objectives, c.user_id
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
                
                (section_id_result, course_id, section_status, generation_progress, 
                 learning_objectives, course_user_id) = section_row
                
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
                
                # If lecture exists AND section is completed, it's complete
                # CRITICAL: Check status too to avoid race condition during final storage
                if delivery_row and section_status == 'completed':
                    return success_response({
                        "section_id": section_id_db,
                        "phase": "complete",
                        "covered_objectives": 0,
                        "total_objectives": 0,
                        "progress_percent": 100,
                        "current_step": "Lecture generation complete",
                    })
        
        # Check section status to determine generation phase
        if section_status == 'in_progress' and generation_progress:
            # Generation is running - use detailed progress from database
            phase = generation_progress.get('phase', 'objectives')
            covered_objectives = generation_progress.get('covered_objectives', [])
            total_objectives = generation_progress.get('total_objectives', len(learning_objectives or []))
            current_step = generation_progress.get('current_step', 'Generating lecture...')
            
            # Calculate progress percentage
            if phase == 'objectives':
                # Objectives: 0-80% (each objective is 80/total)
                progress_percent = int((len(covered_objectives) / (total_objectives + 1)) * 100) if total_objectives > 0 else 0
            elif phase == 'refining':
                # Refining: 80-95%
                progress_percent = 85
            elif phase == 'storing':
                # Storing: 95-100%
                progress_percent = 98
            else:
                progress_percent = 50
            
            return success_response({
                "section_id": section_id_db,
                "phase": phase,
                "covered_objectives": len(covered_objectives),
                "total_objectives": total_objectives,
                "progress_percent": progress_percent,
                "current_step": current_step,
            })
        elif section_status == 'in_progress':
            # Generation started but no progress data yet
            return success_response({
                "section_id": section_id_db,
                "phase": "initializing",
                "covered_objectives": 0,
                "total_objectives": len(learning_objectives or []),
                "progress_percent": 5,
                "current_step": "Initializing lecture generation...",
            })
        elif section_status == 'completed':
            # Section complete but no lecture yet - should not happen
            return success_response({
                "section_id": section_id_db,
                "phase": "not_started",
                "covered_objectives": 0,
                "total_objectives": 0,
                "progress_percent": 0,
                "current_step": "Lecture generation not started",
            })
        else:
            # Status is 'not_started' or other
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
