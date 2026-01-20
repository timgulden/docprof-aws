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
    generate_section_lecture,
    generate_objective_content,
    refine_section_lecture,
    handle_lecture_generated,
)
from shared.core.course_models import (
    CourseState,
    CourseSection,
    Course,
    CoursePreferences,
)
from shared.command_executor import execute_command
from shared.core.commands import RetrieveChunksCommand, SearchCorpusCommand

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Track if we've already ensured the column exists (avoid repeated checks)
_progress_column_ensured = False


def _ensure_progress_column():
    """Ensure generation_progress column exists in course_sections table."""
    global _progress_column_ensured
    if _progress_column_ensured:
        return
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    ALTER TABLE course_sections 
                    ADD COLUMN IF NOT EXISTS generation_progress JSONB DEFAULT NULL
                """)
                conn.commit()
        _progress_column_ensured = True
        logger.info("✓ Ensured generation_progress column exists")
    except Exception as e:
        logger.warning(f"Could not ensure generation_progress column: {e}")


def _update_generation_progress(
    section_id: str,
    phase: str,
    covered_objectives: list,
    total_objectives: int,
    current_step: str
):
    """Update generation progress in database for real-time status tracking."""
    progress_data = {
        "phase": phase,
        "covered_objectives": covered_objectives,
        "total_objectives": total_objectives,
        "current_step": current_step
    }
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE course_sections
                    SET generation_progress = %s::jsonb
                    WHERE section_id = %s::uuid
                    """,
                    (json.dumps(progress_data), section_id)
                )
                conn.commit()
        logger.info(f"Progress update: {current_step}")
    except Exception as e:
        logger.warning(f"Could not update progress: {e}")


def _clear_generation_progress(section_id: str):
    """Clear generation progress after lecture is complete."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE course_sections
                    SET generation_progress = NULL
                    WHERE section_id = %s::uuid
                    """,
                    (section_id,)
                )
                conn.commit()
        logger.info("✓ Progress tracking cleared (lecture complete)")
    except Exception as e:
        logger.warning(f"Could not clear progress: {e}")


def handle_async_generation(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle async lecture generation request (invoked by EventBridge).
    
    Performs the full two-pass generation and stores the result.
    Updates section status and progress tracking.
    """
    section_id = event['section_id']
    course_id = event['course_id']
    user_id = event['user_id']
    
    logger.info(f"Starting async lecture generation for section {section_id}")
    
    # Ensure generation_progress column exists (migration)
    _ensure_progress_column()
    
    try:
        # Perform the full two-pass generation
        lecture_script, delivery_id, model_switch_notification = generate_lecture_for_section(
            section_id=section_id,
            course_id=course_id,
            user_id=user_id
        )
        
        # Mark section as completed and clear progress
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE course_sections
                    SET status = 'completed',
                        completed_at = NOW(),
                        generation_progress = NULL
                    WHERE section_id = %s::uuid
                    """,
                    (section_id,)
                )
                conn.commit()
        
        logger.info(f"✓ Async lecture generation completed for section {section_id}")
        logger.info(f"✓ Delivery ID: {delivery_id}")
        logger.info(f"✓ Section status set to 'completed' and progress cleared")
        
        return {"status": "success", "delivery_id": delivery_id}
        
    except Exception as e:
        logger.error(f"Async lecture generation failed for section {section_id}: {e}", exc_info=True)
        
        # Reset section to not_started (allows retry) and clear progress
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE course_sections
                        SET status = 'not_started', 
                            generation_progress = NULL
                        WHERE section_id = %s::uuid
                        """,
                        (section_id,)
                    )
                    conn.commit()
            logger.info(f"Reset section {section_id} to 'not_started' after error")
        except Exception as db_error:
            logger.error(f"Failed to reset section status: {db_error}")
        
        return {"status": "error", "error": str(e)}


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for retrieving section lecture.
    
    Supports two modes:
    1. API Gateway request (GET /courses/section/{sectionId}/lecture)
       - Returns lecture if available, or triggers async generation
    2. Async generation request (invoked by self)
       - Performs actual two-pass lecture generation
    
    Flow:
    1. Check if lecture already exists in database
    2. If exists: return immediately (200 OK)
    3. If not exists: trigger async generation, return 202 Accepted
    4. Frontend polls /courses/section/{sectionId}/lecture until ready
    
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
    
    Expected event format (Async generation):
    {
        "action": "generate",
        "section_id": "uuid",
        "course_id": "uuid",
        "user_id": "uuid"
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
        # Check if this is an EventBridge async generation request
        if event.get('source') == 'docprof.lecture' and event.get('detail-type') == 'LectureGenerationRequested':
            logger.info("Processing EventBridge async generation request")
            detail = json.loads(event['detail']) if isinstance(event['detail'], str) else event['detail']
            return handle_async_generation(detail)
        
        # Otherwise, it's a normal API Gateway request
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
                
                # CRITICAL: Check if lecture delivery exists FIRST
                # Even if status is 'in_progress', the lecture might be stored
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
                
                # If lecture exists, return it (regardless of section_status)
                if delivery_row:
                    (delivery_id, _, _, lecture_script, delivered_at,
                     duration_actual, user_notes, style_snapshot) = delivery_row
                    
                    logger.info(f"✓ Lecture found for section {section_id_db}, returning it")
                    # Normalize line endings for consistent rendering/offsets
                    lecture_script = lecture_script.replace("\r\n", "\n").replace("\r", "\n")
                    
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
        
        # Lecture doesn't exist - check if generation is in progress
        if section_status == 'in_progress':
            logger.info(f"Lecture generation in progress for section {section_id_db}")
            return success_response({
                "status": "generating",
                "section_id": section_id_db,
                "message": "Lecture generation in progress. Please check back in a moment.",
                "estimated_minutes": int(estimated_minutes),
            }, status_code=202)
        
        # Lecture doesn't exist and not generating - trigger async generation
        logger.info(f"Lecture not found for section {section_id_db}, triggering async generation...")
        
        # Mark section as in_progress
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE course_sections
                    SET status = 'in_progress'
                    WHERE section_id = %s::uuid
                    """,
                    (section_id_db,)
                )
                conn.commit()
        
        logger.info(f"✓ Section status updated to 'in_progress' for {section_id_db}")
        
        # Trigger async generation via EventBridge (works from VPC)
        import boto3
        import json as json_lib
        
        events_client = boto3.client('events')
        
        # Prepare EventBridge event for async generation
        event_detail = {
            'action': 'generate',
            'section_id': section_id_db,
            'course_id': str(course_id),
            'user_id': user_id
        }
        
        # Publish to EventBridge default bus
        events_client.put_events(
            Entries=[
                {
                    'Source': 'docprof.lecture',
                    'DetailType': 'LectureGenerationRequested',
                    'Detail': json_lib.dumps(event_detail),
                }
            ]
        )
        
        logger.info(f"Async generation triggered via EventBridge for section {section_id_db}")
        
        # Return 202 Accepted with status
        return success_response({
            "status": "generating",
            "section_id": section_id_db,
            "message": "Lecture generation started. Please check back in a moment.",
            "estimated_minutes": int(estimated_minutes),
        }, status_code=202)
        
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
) -> tuple[str, str, str]:
    """
    Generate lecture for a section using MAExpert's two-pass approach.
    
    Pass 1: Generate content for each learning objective separately
    Pass 2: Refine and integrate all objectives into cohesive lecture
    
    This orchestrates the full lecture generation workflow:
    1. Load section and course from database
    2. Create CourseState
    3. For each objective:
       - Search for objective-specific chunks
       - Generate content for that objective
       - Append to draft
    4. Refine complete lecture for flow and consistency
    5. Store lecture in database
    
    Returns:
        tuple[str, str, str]: (lecture_script, delivery_id, model_switch_notification)
    
    Raises:
        Exception: If any step fails
    """
    logger.info(f"Starting two-pass lecture generation for section {section_id}")
    logger.info(f"Pass 1: Generate each objective separately, Pass 2: Refine complete lecture")
    
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
             summary, est_min, chunk_ids_raw, status) = section_row
            
            # Debug: Log chunk_ids type and value
            logger.info(f"chunk_ids from DB - type: {type(chunk_ids_raw)}, value: {repr(chunk_ids_raw)}")
            
            # Parse chunk_ids properly - psycopg2 returns PostgreSQL array as list or string
            if isinstance(chunk_ids_raw, list):
                # Already a list (shouldn't happen with default cursor, but handle it)
                chunk_ids = [str(cid) for cid in chunk_ids_raw]
            elif isinstance(chunk_ids_raw, str):
                # String representation of PostgreSQL array: '{}' or '{uuid1,uuid2}'
                # For empty array: '{}'
                if chunk_ids_raw == '{}' or chunk_ids_raw == '':
                    chunk_ids = []
                else:
                    # Parse the array string - strip braces and split by comma
                    # Example: '{uuid1,uuid2}' -> ['uuid1', 'uuid2']
                    chunk_ids = chunk_ids_raw.strip('{}').split(',') if chunk_ids_raw.strip('{}') else []
            else:
                chunk_ids = []
            
            logger.info(f"Parsed chunk_ids - count: {len(chunk_ids)}, values: {chunk_ids[:3] if chunk_ids else 'none'}")
            
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
                chunk_ids=chunk_ids,  # Use the parsed chunk_ids
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
    
    # Step 1: Get section-level chunks (for all objectives)
    logger.info("Step 1: Getting section-level chunks...")
    
    section_chunks = []
    if section.chunk_ids:
        # Section has pre-assigned chunk_ids - retrieve them directly
        logger.info(f"Section has {len(section.chunk_ids)} pre-assigned chunk_ids, retrieving...")
        retrieve_cmd = RetrieveChunksCommand(chunk_ids=section.chunk_ids)
        retrieve_result = execute_command(retrieve_cmd, state=state)
        
        if retrieve_result.get('status') != 'success':
            raise ValueError(f"Failed to retrieve chunks: {retrieve_result.get('error')}")
        
        section_chunks = retrieve_result.get('chunks', [])
    else:
        # No chunk_ids - use vector search based on section title/objectives
        logger.info("No pre-assigned chunk_ids, searching for section-level content...")
        
        # Build search query from section title and objectives
        search_text = f"{section.title}. {' '.join(section.learning_objectives or [])}"
        logger.info(f"Searching for: {search_text[:100]}...")
        
        search_cmd = SearchCorpusCommand(
            query_text=search_text,
            chunk_types=["chapter", "source_summary"],  # Search chapters and summaries
            top_k={"chapter": 5, "source_summary": 2},  # Get 5 chapters, 2 summaries
        )
        search_result = execute_command(search_cmd, state=state)
        
        if search_result.get('status') != 'success':
            logger.warning(f"Search failed: {search_result.get('error')}, proceeding with empty chunks")
        else:
            section_chunks = search_result.get('chunks', [])
    
    logger.info(f"Found {len(section_chunks)} section-level chunks")
    
    # PASS 1: Generate content for each objective separately
    logger.info("=" * 60)
    logger.info("PASS 1: Generate objective-by-objective content")
    logger.info("=" * 60)
    
    objective_contents = []
    all_chunks_used = set()  # Track all chunks to deduplicate
    total_objectives = len(section.learning_objectives or [])
    
    # Initialize progress tracking
    _update_generation_progress(
        section_id=section_id,
        phase="objectives",
        covered_objectives=[],
        total_objectives=total_objectives,
        current_step=f"Starting lecture generation (0 of {total_objectives} objectives completed)..."
    )
    
    for idx, objective in enumerate(section.learning_objectives or [], 1):
        logger.info(f"\n--- Objective {idx}/{len(section.learning_objectives)}: {objective[:60]}...")
        
        # Step 1a: Search for objective-specific chunks
        logger.info(f"  Searching for objective-specific chunks...")
        search_cmd = SearchCorpusCommand(
            query_text=objective,
            chunk_types=["chapter", "source_summary"],
            top_k={"chapter": 5, "source_summary": 2},  # 5 chapters, 2 summaries per objective
        )
        search_result = execute_command(search_cmd, state=state)
        
        objective_chunks = []
        if search_result.get('status') == 'success':
            objective_chunks = search_result.get('chunks', [])
        
        # Combine section chunks + objective chunks, deduplicate
        combined_chunks = section_chunks + objective_chunks
        unique_chunks = []
        seen_ids = set()
        for chunk in combined_chunks:
            chunk_id = chunk.get('chunk_id')
            if chunk_id not in seen_ids:
                unique_chunks.append(chunk)
                seen_ids.add(chunk_id)
                all_chunks_used.add(chunk_id)
        
        logger.info(f"  Using {len(unique_chunks)} chunks ({len(section_chunks)} section + {len(objective_chunks)} objective, deduplicated)")
        
        # Step 1b: Generate content for this objective
        logger.info(f"  Generating content for objective {idx}...")
        
        result = generate_objective_content(
            state=state,
            objective_index=idx - 1,  # Convert to 0-based index
            chunks=unique_chunks
        )
        state = result.new_state
        
        if not result.commands:
            raise ValueError(f"Expected LLMCommand from generate_objective_content for objective {idx}")
        
        llm_cmd = result.commands[0]
        llm_result = execute_command(llm_cmd, state=state)
        
        if llm_result.get('status') != 'success':
            raise ValueError(f"Failed to generate content for objective {idx}: {llm_result.get('error')}")
        
        objective_content = llm_result.get('content', '')
        logger.info(f"  ✓ Generated {len(objective_content)} chars for objective {idx}")
        
        # Update progress after each objective
        covered = list(range(idx))  # [0, 1, 2, ...] for completed objectives
        progress_percent = int((idx / (total_objectives + 1)) * 100)  # +1 for refinement step
        _update_generation_progress(
            section_id=section_id,
            phase="objectives",
            covered_objectives=covered,
            total_objectives=total_objectives,
            current_step=f"Generating objective {idx} of {total_objectives}..."
        )
        
        objective_contents.append({
            'objective': objective,
            'content': objective_content,
            'index': idx
        })
    
    logger.info(f"\n✓ Pass 1 complete: Generated content for {len(objective_contents)} objectives")
    logger.info(f"✓ Total unique chunks used: {len(all_chunks_used)}")
    
    # Update progress: all objectives complete, starting refinement
    _update_generation_progress(
        section_id=section_id,
        phase="refining",
        covered_objectives=list(range(total_objectives)),
        total_objectives=total_objectives,
        current_step=f"All objectives complete. Refining lecture for flow and consistency..."
    )
    
    # PASS 2: Refine and integrate all objectives into cohesive lecture
    logger.info("=" * 60)
    logger.info("PASS 2: Refine and integrate into cohesive lecture")
    logger.info("=" * 60)
    
    # Combine all objective contents into a draft
    draft_lecture = "\n\n".join([
        f"## Learning Objective {obj['index']}: {obj['objective']}\n\n{obj['content']}"
        for obj in objective_contents
    ])
    
    logger.info(f"Draft lecture: {len(draft_lecture)} chars")
    logger.info("Refining lecture for flow, consistency, and pedagogical quality...")
    
    # Update state with the draft
    state = state.model_copy(update={"current_section_draft": draft_lecture})
    
    result = refine_section_lecture(state=state)
    state = result.new_state
    
    if not result.commands:
        raise ValueError("Expected LLMCommand from refine_section_lecture")
    
    llm_cmd = result.commands[0]
    llm_result = execute_command(llm_cmd, state=state)
    
    if llm_result.get('status') != 'success':
        raise ValueError(f"Failed to refine lecture: {llm_result.get('error')}")
    
    lecture_script = llm_result.get('content', '')
    model_switch_notification = llm_result.get('model_switch_notification')
    
    if model_switch_notification:
        logger.warning(f"Model switch notification: {model_switch_notification}")
    
    logger.info(f"✓ Pass 2 complete: Refined lecture ({len(lecture_script)} chars)")
    logger.info("=" * 60)
    
    # Update progress: refinement in progress (don't show 100% until stored!)
    _update_generation_progress(
        section_id=section_id,
        phase="refining",
        covered_objectives=list(range(total_objectives)),
        total_objectives=total_objectives,
        current_step="Refinement complete. Saving lecture to database..."
    )
    
    # Step 3: Store lecture delivery
    logger.info("Step 3: Storing lecture...")
    result = handle_lecture_generated(state, lecture_script)
    state = result.new_state
    
    if not result.commands:
        raise ValueError("Expected StoreLectureCommand from handle_lecture_generated")
    
    store_cmd = result.commands[0]
    store_result = execute_command(store_cmd, state=state)
    
    if store_result.get('status') != 'success':
        raise ValueError(f"Failed to store lecture: {store_result.get('error')}")
    
    delivery_id = store_result.get('delivery_id')
    logger.info(f"✓ Lecture stored with delivery_id: {delivery_id}")
    
    # Clear progress tracking (lecture is stored and ready)
    _clear_generation_progress(section_id)
    
    return lecture_script, delivery_id, model_switch_notification
