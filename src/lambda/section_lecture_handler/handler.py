"""
Section Lecture Handler - GET /courses/section/{sectionId}/lecture

Returns lecture script for a section, or triggers async generation if not available.
Used by the frontend SectionPlayer component.
"""

import json
import logging
import uuid
from typing import Dict, Any, Optional
from datetime import datetime

from shared.db_utils import get_db_connection
from shared.response import success_response, error_response
from shared.logic.courses import (
    prepare_section_delivery,
    generate_section_lecture,
    handle_lecture_generated,
)
from shared.core.course_models import (
    CourseState,
    CourseSection,
    Course,
    CoursePreferences,
)
from shared.command_executor import execute_command
from shared.core.commands import RetrieveChunksCommand

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for retrieving section lecture.
    
    Flow:
    1. Check if lecture already exists in database
    2. If exists: return immediately (200 OK)
    3. If not exists: trigger async generation, return 202 Accepted
    4. Frontend polls /courses/section/{sectionId}/generation-status for progress
    
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
    
    Returns (200 OK - lecture ready):
    {
        "section_id": "uuid",
        "lecture_script": "...",
        "estimated_minutes": 30,
        "delivery_id": "uuid",
        "figures": [...]
    }
    
    Returns (202 Accepted - generation in progress):
    {
        "message": "Lecture generation in progress",
        "section_id": "uuid",
        "status": "generating"
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
        
        logger.info(f"Fetching lecture for section {section_id_db}, user {user_id}")
        
        # Check if lecture already exists
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Get section to verify ownership
                cur.execute(
                    """
                    SELECT cs.section_id, cs.course_id, cs.title, cs.learning_objectives,
                           cs.estimated_minutes, cs.status, c.user_id
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
                
                (section_id_result, course_id, section_title, learning_objectives,
                 estimated_minutes, section_status, course_user_id) = section_row
                
                # Verify user owns this course
                if str(course_user_id) != user_id:
                    return error_response(
                        "Access denied: you do not own this course",
                        status_code=403
                    )
                
                # Check if lecture delivery exists
                cur.execute(
                    """
                    SELECT delivery_id, section_id, user_id, lecture_script,
                           delivered_at, duration_actual_minutes, user_notes, style_snapshot
                    FROM section_deliveries
                    WHERE section_id = %s::uuid AND user_id = %s::uuid
                    ORDER BY delivered_at DESC
                    LIMIT 1
                    """,
                    (section_id_db, user_id)
                )
                delivery_row = cur.fetchone()
                
                # If lecture exists, return it
                if delivery_row:
                    (delivery_id, _, _, lecture_script, delivered_at,
                     duration_actual, user_notes, style_snapshot) = delivery_row
                    
                    logger.info(f"Lecture found for section {section_id_db}")
                    
                    # Get figures for section (if any)
                    # TODO: Implement figure retrieval when figure system is ready
                    figures = []
                    
                    return success_response({
                        "section_id": section_id_db,
                        "lecture_script": lecture_script,
                        "estimated_minutes": int(estimated_minutes),
                        "delivery_id": str(delivery_id),
                        "figures": figures,
                        "delivered_at": delivered_at.isoformat() if delivered_at else None,
                    })
        
        # Lecture doesn't exist - generate it synchronously
        logger.info(f"Lecture not found for section {section_id_db}, generating now...")
        
        # For P0, we'll generate synchronously (simple approach)
        # This keeps things simple and avoids complexity of async generation
        # Generate lecture using pure logic + command execution
        try:
            lecture_script, delivery_id, model_switch_notification = generate_lecture_for_section(
                section_id=section_id_db,
                course_id=str(course_id),
                user_id=user_id
            )
            
            # Build response
            response_data = {
                "section_id": section_id_db,
                "lecture_script": lecture_script,
                "estimated_minutes": int(estimated_minutes),
                "delivery_id": delivery_id,
                "figures": [],  # TODO: Add figure retrieval
                "delivered_at": datetime.utcnow().isoformat(),
            }
            
            # Include model switch notification if present
            if model_switch_notification:
                response_data["model_notification"] = model_switch_notification
            
            return success_response(response_data)
            
        except Exception as gen_error:
            logger.error(f"Error generating lecture: {gen_error}", exc_info=True)
            # If generation fails, return error (not 202)
            return error_response(
                f"Failed to generate lecture: {str(gen_error)}",
                status_code=500
            )
        
    except Exception as e:
        logger.error(f"Error retrieving section lecture: {e}", exc_info=True)
        return error_response(
            f"Failed to retrieve section lecture: {str(e)}",
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


def http_response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create HTTP response with proper CORS headers.
    """
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
        },
        "body": json.dumps(body, default=str),
    }


def generate_lecture_for_section(
    section_id: str,
    course_id: str,
    user_id: str
) -> tuple[str, str]:
    """
    Generate lecture for a section synchronously.
    
    This orchestrates the full lecture generation workflow:
    1. Load section and course from database
    2. Create CourseState
    3. Retrieve chunks for section
    4. Generate lecture via LLM
    5. Store lecture in database
    
    Returns:
        tuple[str, str]: (lecture_script, delivery_id)
    
    Raises:
        Exception: If any step fails
    """
    logger.info(f"Starting synchronous lecture generation for section {section_id}")
    
    # Load section and course from database
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Get section
            cur.execute("""
                SELECT 
                    section_id, course_id, parent_section_id, order_index,
                    title, learning_objectives, content_summary,
                    estimated_minutes, chunk_ids, status
                FROM course_sections
                WHERE section_id = %s::uuid
            """, (section_id,))
            section_row = cur.fetchone()
            
            if not section_row:
                raise ValueError(f"Section not found: {section_id}")
            
            (sec_id, crs_id, parent_id, order_idx, title, objectives,
             summary, est_min, chunk_ids, status) = section_row
            
            # Convert to CourseSection model
            section = CourseSection(
                section_id=str(sec_id),
                course_id=str(crs_id),
                parent_section_id=str(parent_id) if parent_id else None,
                order_index=int(order_idx),
                title=title,
                learning_objectives=list(objectives) if objectives else [],
                content_summary=summary,
                estimated_minutes=int(est_min),
                chunk_ids=[str(cid) for cid in chunk_ids] if chunk_ids else [],
                status=status,
                created_at=datetime.utcnow(),
            )
            
            # Get course
            cur.execute("""
                SELECT 
                    course_id, user_id, title, original_query,
                    estimated_hours, preferences, status
                FROM courses
                WHERE course_id = %s::uuid
            """, (course_id,))
            course_row = cur.fetchone()
            
            if not course_row:
                raise ValueError(f"Course not found: {course_id}")
            
            (crs_id_res, usr_id, crs_title, query, est_hours, prefs_json, crs_status) = course_row
            
            # Parse preferences
            if isinstance(prefs_json, str):
                prefs_dict = json.loads(prefs_json)
            else:
                prefs_dict = prefs_json or {}
            
            preferences = CoursePreferences(**prefs_dict)
            
            # Convert to Course model
            course = Course(
                course_id=str(crs_id_res),
                user_id=str(usr_id),
                title=crs_title,
                original_query=query,
                estimated_hours=float(est_hours),
                created_at=datetime.utcnow(),
                last_modified=datetime.utcnow(),
                preferences=preferences,
                status=crs_status,
            )
    
    # Create CourseState for logic layer
    state = CourseState(
        session_id=section_id,  # Use section_id as session_id for this generation
        current_course=course,
        current_section=section,
    )
    
    # Step 1: Prepare section delivery (gets RetrieveChunksCommand)
    logger.info("Step 1: Preparing section delivery...")
    result = prepare_section_delivery(state, section)
    state = result.new_state
    
    # Step 2: Execute RetrieveChunksCommand to get chunks
    logger.info("Step 2: Retrieving chunks...")
    if not result.commands or not isinstance(result.commands[0], RetrieveChunksCommand):
        # If no chunks needed or different command, handle appropriately
        # For simplicity, assume we always need chunks
        raise ValueError("Expected RetrieveChunksCommand from prepare_section_delivery")
    
    retrieve_cmd = result.commands[0]
    retrieve_result = execute_command(retrieve_cmd, state=state)
    
    if retrieve_result.get('status') != 'success':
        raise ValueError(f"Failed to retrieve chunks: {retrieve_result.get('error')}")
    
    chunks = retrieve_result.get('chunks', [])
    logger.info(f"Retrieved {len(chunks)} chunks for lecture")
    
    # Step 3: Generate section lecture (gets LLMCommand)
    logger.info("Step 3: Generating lecture script...")
    result = generate_section_lecture(state, chunks)
    state = result.new_state
    
    # Step 4: Execute LLMCommand to generate lecture
    if not result.commands:
        raise ValueError("Expected LLMCommand from generate_section_lecture")
    
    llm_cmd = result.commands[0]
    llm_result = execute_command(llm_cmd, state=state)
    
    if llm_result.get('status') != 'success':
        raise ValueError(f"Failed to generate lecture: {llm_result.get('error')}")
    
    lecture_script = llm_result.get('content', '')  # Use 'content' not 'response'
    model_switch_notification = llm_result.get('model_switch_notification')
    
    if model_switch_notification:
        logger.warning(f"Model switch notification: {model_switch_notification}")
    
    logger.info(f"Generated lecture script ({len(lecture_script)} chars)")
    
    # Step 5: Finalize delivery (gets StoreLectureCommand)
    logger.info("Step 5: Finalizing delivery...")
    result = handle_lecture_generated(state, lecture_script)
    state = result.new_state
    
    # Step 6: Execute StoreLectureCommand to save lecture
    if not result.commands:
        raise ValueError("Expected StoreLectureCommand from handle_lecture_generated")
    
    store_cmd = result.commands[0]
    store_result = execute_command(store_cmd, state=state)
    
    if store_result.get('status') != 'success':
        raise ValueError(f"Failed to store lecture: {store_result.get('error')}")
    
    delivery_id = store_result.get('delivery_id')
    logger.info(f"✓ Lecture stored with delivery_id: {delivery_id}")
    
    return lecture_script, delivery_id, model_switch_notification
