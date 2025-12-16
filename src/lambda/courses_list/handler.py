"""
Courses List Lambda Handler
Fetches all courses for the authenticated user from the database
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from shared.db_utils import get_db_connection
from shared.response import success_response, error_response

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle GET /courses request to fetch all courses for the authenticated user.
    
    Extracts user_id from Cognito token in requestContext.authorizer.claims.sub
    Returns list of courses with:
    - courseId (course_id as string)
    - title
    - estimatedHours (estimated_hours)
    - status
    - createdAt (created_at)
    """
    try:
        # Extract user_id from Cognito token
        # API Gateway with Cognito authorizer puts claims in requestContext.authorizer.claims
        user_id = extract_user_id(event)
        
        if not user_id:
            return error_response(
                "Missing user authentication. Please log in.",
                status_code=401
            )
        
        logger.info(f"Fetching courses for user_id: {user_id}")
        courses = fetch_user_courses(user_id)
        
        # Format response to match frontend expectations
        formatted_courses = [
            {
                "courseId": str(course["course_id"]),
                "title": course["title"],
                "estimatedHours": float(course["estimated_hours"]),
                "status": course["status"],
                "createdAt": course["created_at"].isoformat() if course["created_at"] else None,
            }
            for course in courses
        ]
        
        return success_response(formatted_courses)
        
    except Exception as e:
        logger.error(f"Error fetching courses: {e}", exc_info=True)
        return error_response(f"Failed to fetch courses: {str(e)}", 500)


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


def fetch_user_courses(user_id: str) -> List[Dict[str, Any]]:
    """
    Fetch all courses for a specific user from the database.
    
    Args:
        user_id: Cognito user ID (UUID string)
    
    Returns:
        List of course dictionaries
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    course_id,
                    user_id,
                    title,
                    original_query,
                    estimated_hours,
                    created_at,
                    last_modified,
                    status
                FROM courses
                WHERE user_id = %s::uuid
                ORDER BY created_at DESC
            """, (user_id,))
            
            rows = cur.fetchall()
            
            courses = []
            for row in rows:
                (course_id, user_id_db, title, original_query, estimated_hours,
                 created_at, last_modified, status) = row
                
                courses.append({
                    "course_id": course_id,
                    "user_id": user_id_db,
                    "title": title,
                    "original_query": original_query,
                    "estimated_hours": estimated_hours,
                    "created_at": created_at,
                    "last_modified": last_modified,
                    "status": status,
                })
            
            logger.info(f"Found {len(courses)} courses for user {user_id}")
            return courses
