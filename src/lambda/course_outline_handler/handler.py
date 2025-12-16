"""
Course Outline Handler - GET /courses/{courseId}/outline

Returns the complete course outline with hierarchical parts and sections structure.
Used by the frontend CourseDashboard component.
"""

import json
import logging
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime

from shared.db_utils import get_db_connection
from shared.response import success_response, error_response

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for retrieving course outline.
    
    Expected event format (API Gateway):
    {
        "pathParameters": {
            "courseId": "uuid-here"
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
        "course_id": "uuid",
        "title": "Course Title",
        "original_query": "Learn DCF valuation",
        "parts": [
            {
                "section_id": "part-uuid",
                "title": "Part 1: Introduction",
                "estimated_minutes": 60,
                "status": "not_started",
                "sections": [
                    {
                        "section_id": "section-uuid",
                        "title": "Section 1.1",
                        "learning_objectives": ["obj1", "obj2"],
                        "estimated_minutes": 30,
                        "status": "not_started",
                        ...
                    }
                ],
                "total_sections": 2,
                "completed_sections": 0
            }
        ],
        "sections": [...],  // Flat list for backward compatibility
        "total_sections": 10,
        "completed_sections": 3,
        "total_minutes": 180,
        "preferences": {
            "depth": "moderate",
            "presentation_style": "conversational",
            "pace": "moderate"
        }
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
        
        # Extract course_id from path parameters
        path_params = event.get('pathParameters') or {}
        course_id_str = path_params.get('courseId')
        
        if not course_id_str:
            return error_response(
                "Missing courseId in path parameters",
                status_code=400
            )
        
        # Validate UUID format
        try:
            course_id_uuid = uuid.UUID(course_id_str)
            course_id_db = str(course_id_uuid)
        except ValueError:
            return error_response(
                f"Invalid courseId format: {course_id_str}",
                status_code=400
            )
        
        logger.info(f"Fetching outline for course {course_id_db}, user {user_id}")
        
        # Query course and sections from database
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
                    WHERE course_id = %s::uuid AND user_id = %s::uuid
                    """,
                    (course_id_db, user_id)
                )
                course_row = cur.fetchone()
                
                if not course_row:
                    return error_response(
                        f"Course not found or access denied: {course_id_str}",
                        status_code=404
                    )
                
                # Parse course data
                (course_id_result, user_id_result, title, original_query, 
                 estimated_hours, created_at, last_modified, 
                 preferences_json, status) = course_row
                
                # Parse preferences JSONB
                try:
                    if isinstance(preferences_json, str):
                        preferences = json.loads(preferences_json)
                    else:
                        preferences = preferences_json or {}
                except Exception as e:
                    logger.warning(f"Failed to parse preferences: {e}")
                    preferences = {}
                
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
            
            # Convert arrays to lists
            chunk_ids_list = parse_pg_array(chunk_ids)
            prerequisites_list = parse_pg_array(prerequisites)
            learning_objectives_list = list(learning_objectives) if learning_objectives else []
            
            section_dict = {
                "section_id": str(section_id),
                "course_id": str(course_id_sec),
                "parent_section_id": str(parent_section_id) if parent_section_id else None,
                "order_index": int(order_index),
                "title": title_sec,
                "learning_objectives": learning_objectives_list,
                "content_summary": content_summary,
                "estimated_minutes": int(estimated_minutes),
                "chunk_ids": chunk_ids_list,
                "status": status_sec,
                "completed_at": completed_at.isoformat() if completed_at else None,
                "can_standalone": bool(can_standalone),
                "prerequisites": prerequisites_list,
                "created_at": created_at_sec.isoformat() if isinstance(created_at_sec, datetime) else str(created_at_sec),
            }
            sections.append(section_dict)
        
        # Build hierarchical parts structure
        parts = build_parts_hierarchy(sections)
        
        # Calculate totals
        total_sections = len([s for s in sections if not s.get('parent_section_id')])  # Count only leaf sections
        completed_sections = len([s for s in sections if s['status'] == 'completed' and not s.get('parent_section_id')])
        total_minutes = sum(s['estimated_minutes'] for s in sections if not s.get('parent_section_id'))
        
        # Return outline
        return success_response({
            "course_id": course_id_db,
            "title": title,
            "original_query": original_query,
            "parts": parts,
            "sections": sections,  # Flat list for backward compatibility
            "total_sections": total_sections,
            "completed_sections": completed_sections,
            "total_minutes": total_minutes,
            "preferences": preferences,
        })
        
    except Exception as e:
        logger.error(f"Error retrieving course outline: {e}", exc_info=True)
        return error_response(
            f"Failed to retrieve course outline: {str(e)}",
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


def parse_pg_array(pg_array: Any) -> List[str]:
    """
    Parse PostgreSQL array to Python list.
    
    Handles:
    - None -> []
    - List -> List of strings
    - String "{}" -> []
    """
    if pg_array is None:
        return []
    elif isinstance(pg_array, list):
        return [str(item) for item in pg_array if item is not None]
    elif isinstance(pg_array, str):
        if pg_array == "{}" or pg_array == "":
            return []
        logger.warning(f"Unexpected string array format: {pg_array}")
        return []
    else:
        logger.warning(f"Unexpected array type: {type(pg_array)}")
        return []


def build_parts_hierarchy(sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Build hierarchical parts structure from flat sections list.
    
    Two cases:
    1. Hierarchical: Parts are sections with parent_section_id = None,
       child sections have parent_section_id = part section_id
    2. Flat: All sections have parent_section_id = None (no hierarchy)
       Create a single default "Main" part containing all sections
    
    Returns:
        List of parts with nested sections
    """
    # Separate parts (parent sections) from child sections
    parts_dict = {}
    child_sections_dict = {}
    top_level_sections = []  # Sections with no parent
    
    for section in sections:
        if section.get('parent_section_id') is None:
            top_level_sections.append(section)
        else:
            # This is a child section
            parent_id = section['parent_section_id']
            if parent_id not in child_sections_dict:
                child_sections_dict[parent_id] = []
            child_sections_dict[parent_id].append(section)
    
    # Check if we have a hierarchical structure
    # Hierarchical: top-level sections have children
    # Flat: top-level sections have NO children
    has_hierarchy = any(
        section['section_id'] in child_sections_dict
        for section in top_level_sections
    )
    
    if has_hierarchy:
        # Hierarchical structure - build parts from top-level sections
        for section in top_level_sections:
            section_id = section['section_id']
            parts_dict[section_id] = {
                "section_id": section_id,
                "title": section['title'],
                "estimated_minutes": section['estimated_minutes'],
                "status": section['status'],
                "sections": child_sections_dict.get(section_id, []),
                "total_sections": len(child_sections_dict.get(section_id, [])),
                "completed_sections": len([
                    s for s in child_sections_dict.get(section_id, [])
                    if s['status'] == 'completed'
                ]),
            }
        
        # Return parts in order
        parts_list = sorted(parts_dict.values(), key=lambda p: p['sections'][0]['order_index'] if p['sections'] else 0)
        return parts_list
    
    else:
        # Flat structure - all sections are top-level
        # Create single "Main" part containing all sections
        if not top_level_sections:
            return []
        
        return [{
            "section_id": "main",  # Virtual part ID
            "title": "Course Content",
            "estimated_minutes": sum(s['estimated_minutes'] for s in top_level_sections),
            "status": "in_progress" if any(s['status'] == 'in_progress' for s in top_level_sections) else "not_started",
            "sections": top_level_sections,
            "total_sections": len(top_level_sections),
            "completed_sections": len([s for s in top_level_sections if s['status'] == 'completed']),
        }]
