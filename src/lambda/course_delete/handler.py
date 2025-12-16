"""
Delete course Lambda - removes course and all associated data.
Follows MAExpert's cascading delete pattern.
"""

import json
import logging
import os
from typing import Any, Dict

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Delete a course and all associated data.
    
    Path: DELETE /courses/{courseId}
    Auth: Requires Cognito user_id
    
    Cascading delete (follows MAExpert logic):
    1. lecture_qa_records (if table exists)
    2. section_deliveries
    3. course_sections  
    4. course_state (DynamoDB)
    5. courses (with user_id ownership check)
    
    Returns 204 No Content on success, 404 if not found/no permission.
    """
    try:
        from shared.db_utils import get_db_connection
        from shared.response import error_response
        import boto3
        
        # Extract user_id from Cognito authorizer
        user_id = event.get('requestContext', {}).get('authorizer', {}).get('claims', {}).get('sub')
        if not user_id:
            logger.warning("Missing user_id in request context")
            return error_response(401, "Unauthorized - missing user_id")
        
        # Extract course_id from path
        course_id = event.get('pathParameters', {}).get('courseId')
        if not course_id:
            return error_response(400, "Missing courseId in path")
        
        logger.info(f"Deleting course {course_id} for user {user_id}")
        
        # Cascading delete in database (follows MAExpert pattern)
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # 1. Delete lecture Q&A records (if table exists)
                # Check if table exists first (may not be created yet)
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'lecture_qa_records'
                    )
                """)
                qa_table_exists = cur.fetchone()[0]
                
                if qa_table_exists:
                    cur.execute("""
                        DELETE FROM lecture_qa_records
                        WHERE section_id IN (
                            SELECT section_id FROM course_sections WHERE course_id = %s
                        )
                    """, (course_id,))
                    qa_deleted = cur.rowcount
                    logger.info(f"Deleted {qa_deleted} Q&A records")
                
                # 2. Delete section deliveries (lecture content, audio)
                cur.execute("""
                    DELETE FROM section_deliveries
                    WHERE section_id IN (
                        SELECT section_id FROM course_sections WHERE course_id = %s
                    )
                """, (course_id,))
                deliveries_deleted = cur.rowcount
                logger.info(f"Deleted {deliveries_deleted} section deliveries")
                
                # 3. Delete course sections
                cur.execute("""
                    DELETE FROM course_sections
                    WHERE course_id = %s
                    RETURNING section_id
                """, (course_id,))
                sections_deleted = cur.rowcount
                logger.info(f"Deleted {sections_deleted} course sections")
                
                # 4. Delete course (with user_id ownership check - security critical!)
                cur.execute("""
                    DELETE FROM courses
                    WHERE course_id = %s AND user_id = %s
                    RETURNING course_id
                """, (course_id, user_id))
                
                deleted_course = cur.fetchone()
                if not deleted_course:
                    logger.warning(f"Course {course_id} not found or user {user_id} doesn't own it")
                    conn.rollback()
                    return error_response(
                        404, 
                        "Course not found or you don't have permission to delete it"
                    )
                
                conn.commit()
                logger.info(f"Successfully deleted course {course_id} from database")
        
        # 5. Delete course state from DynamoDB (best effort - don't fail if missing)
        try:
            dynamodb = boto3.resource('dynamodb')
            table_name = f"docprof-{os.getenv('ENVIRONMENT', 'dev')}-course-state"
            table = dynamodb.Table(table_name)
            table.delete_item(Key={'course_id': course_id})
            logger.info(f"Deleted course state from DynamoDB: {table_name}")
        except Exception as e:
            logger.warning(f"Could not delete DynamoDB state (non-critical): {e}")
            # Don't fail - state cleanup is best-effort
        
        logger.info(f"Course {course_id} fully deleted for user {user_id}")
        
        # Return 204 No Content (success with no response body)
        return {
            'statusCode': 204,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,Authorization',
                'Access-Control-Allow-Methods': 'DELETE,OPTIONS',
            },
        }
        
    except Exception as e:
        logger.error(f"Error deleting course {course_id}: {e}", exc_info=True)
        return error_response(500, f"Failed to delete course: {str(e)}")
