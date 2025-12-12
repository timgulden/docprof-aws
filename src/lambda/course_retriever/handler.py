"""
Course Retriever Handler - GET course by ID.

Retrieves course and all sections from Aurora database.
"""

import json
import logging
import uuid
from typing import Dict, Any, Optional
from datetime import datetime

from shared.db_utils import get_db_connection
from shared.core.course_models import Course, CourseSection, CoursePreferences
from shared.response import success_response, error_response

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for retrieving a course by ID.
    
    Expected event format (API Gateway):
    {
        "pathParameters": {
            "courseId": "uuid-here"
        }
    }
    """
    try:
        # Extract course_id from path parameters or query string
        # Support both "course" (singular) and "courses/{courseId}" paths
        path_params = event.get('pathParameters') or {}
        query_params = event.get('queryStringParameters') or {}
        
        course_id_str = (
            path_params.get('courseId') or 
            path_params.get('course_id') or
            query_params.get('courseId') or
            query_params.get('course_id')
        )
        
        if not course_id_str:
            return error_response(
                "Missing courseId in path parameters or query string",
                status_code=400
            )
        
        # Validate UUID format
        try:
            course_id_uuid = uuid.UUID(course_id_str)
            # Convert to string for psycopg2 (it handles UUID strings, not UUID objects)
            course_id_db = str(course_id_uuid)
        except ValueError:
            return error_response(
                f"Invalid courseId format: {course_id_str}",
                status_code=400
            )
        
        # Query course from database
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Get course
                cur.execute(
                    """
                    SELECT 
                        course_id, user_id, title, original_query,
                        estimated_hours, created_at, last_modified,
                        preferences, status
                    FROM courses
                    WHERE course_id = %s::uuid
                    """,
                    (course_id_db,)
                )
                course_row = cur.fetchone()
                
                if not course_row:
                    return error_response(
                        f"Course not found: {course_id_str}",
                        status_code=404
                    )
                
                # Parse course data
                course_id_db, user_id, title, original_query, estimated_hours, \
                    created_at, last_modified, preferences_json, status = course_row
                
                # Parse preferences JSONB
                try:
                    if isinstance(preferences_json, str):
                        preferences_dict = json.loads(preferences_json)
                    else:
                        preferences_dict = preferences_json
                    preferences = CoursePreferences(**preferences_dict)
                except Exception as e:
                    logger.warning(f"Failed to parse preferences, using defaults: {e}")
                    preferences = CoursePreferences()
                
                course = Course(
                    course_id=str(course_id_db),
                    user_id=str(user_id),
                    title=title,
                    original_query=original_query,
                    estimated_hours=float(estimated_hours),
                    created_at=created_at if isinstance(created_at, datetime) else datetime.fromisoformat(str(created_at)),
                    last_modified=last_modified if isinstance(last_modified, datetime) else datetime.fromisoformat(str(last_modified)),
                    preferences=preferences,
                    status=status,
                )
                
                # Get all sections for this course
                cur.execute(
                    """
                    SELECT 
                        section_id, course_id, parent_section_id, order_index,
                        title, learning_objectives, content_summary,
                        estimated_minutes, chunk_ids, status,
                        completed_at, can_standalone, prerequisites, created_at
                    FROM course_sections
                    WHERE course_id = %s::uuid
                    ORDER BY order_index ASC
                    """,
                    (course_id_db,)
                )
                section_rows = cur.fetchall()
                
                # Parse sections
                sections = []
                for row in section_rows:
                    (section_id, course_id_sec, parent_section_id, order_index,
                     title_sec, learning_objectives, content_summary,
                     estimated_minutes, chunk_ids, status_sec,
                     completed_at, can_standalone, prerequisites, created_at_sec) = row
                    
                    # Convert UUID arrays to string lists
                    # psycopg2 returns PostgreSQL arrays as Python lists
                    # Handle list, None, and edge cases
                    if chunk_ids is None:
                        chunk_ids_list = []
                    elif isinstance(chunk_ids, list):
                        # Filter out any None values and convert to strings
                        chunk_ids_list = [str(cid) for cid in chunk_ids if cid is not None]
                    elif isinstance(chunk_ids, str):
                        # Edge case: psycopg2 might return empty arrays as "{}" string
                        if chunk_ids == "{}" or chunk_ids == "":
                            chunk_ids_list = []
                        else:
                            # Try to parse PostgreSQL array format "{uuid1,uuid2}"
                            logger.warning(f"chunk_ids is a string (unexpected): {chunk_ids}")
                            chunk_ids_list = []
                    else:
                        logger.warning(f"chunk_ids is unexpected type: {type(chunk_ids)}, value: {chunk_ids}")
                        chunk_ids_list = []
                    
                    if prerequisites is None:
                        prerequisites_list = []
                    elif isinstance(prerequisites, list):
                        # Filter out any None values and convert to strings
                        prerequisites_list = [str(pid) for pid in prerequisites if pid is not None]
                    elif isinstance(prerequisites, str):
                        # Edge case: psycopg2 might return empty arrays as "{}" string
                        if prerequisites == "{}" or prerequisites == "":
                            prerequisites_list = []
                        else:
                            # Try to parse PostgreSQL array format "{uuid1,uuid2}"
                            logger.warning(f"prerequisites is a string (unexpected): {prerequisites}")
                            prerequisites_list = []
                    else:
                        logger.warning(f"prerequisites is unexpected type: {type(prerequisites)}, value: {prerequisites}")
                        prerequisites_list = []
                    
                    # Convert TEXT[] to list
                    learning_objectives_list = list(learning_objectives) if learning_objectives else []
                    
                    section = CourseSection(
                        section_id=str(section_id),
                        course_id=str(course_id_sec),
                        parent_section_id=str(parent_section_id) if parent_section_id else None,
                        order_index=int(order_index),
                        title=title_sec,
                        learning_objectives=learning_objectives_list,
                        content_summary=content_summary,
                        estimated_minutes=int(estimated_minutes),
                        chunk_ids=chunk_ids_list,
                        status=status_sec,
                        completed_at=completed_at if completed_at else None,
                        can_standalone=bool(can_standalone),
                        prerequisites=prerequisites_list,
                        created_at=created_at_sec if isinstance(created_at_sec, datetime) else datetime.fromisoformat(str(created_at_sec)),
                    )
                    sections.append(section)
        
        # Return course with sections
        # model_dump() returns dict with datetime objects, which will be serialized by success_response
        return success_response({
            'course': course.model_dump(),
            'sections': [s.model_dump() for s in sections],
            'section_count': len(sections),
        })
        
    except Exception as e:
        logger.error(f"Error retrieving course: {e}", exc_info=True)
        return error_response(
            f"Failed to retrieve course: {str(e)}",
            status_code=500
        )
