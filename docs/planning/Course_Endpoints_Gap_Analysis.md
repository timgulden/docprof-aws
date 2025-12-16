# Course Endpoints - Gap Analysis

## MAExpert (Working) vs AWS (Current)

### ✅ Already Implemented in AWS

| Endpoint | Method | Purpose | Status |
|----------|--------|---------|--------|
| `/courses` | GET | List all courses | ✅ Working |
| `/courses/create` | POST | Create new course | ✅ Working |
| `/courses/{courseId}/outline` | GET | Get course outline | ✅ Working |
| `/courses/section/{sectionId}/lecture` | GET | Get lecture content | ✅ Working |
| `/courses/section/{sectionId}/generation-status` | GET | Poll generation progress | ✅ Working |
| `/courses/section/{sectionId}/complete` | POST | Mark section complete | ✅ Working |

### 🔴 Missing in AWS (Needed for Full Functionality)

#### Priority 1 - Critical for Basic UX

| Endpoint | Method | MAExpert | Logic Location | Estimate |
|----------|--------|----------|----------------|----------|
| `/courses/{courseId}` | DELETE | ✅ | `db_client.delete_course()` | 2-3 hours |
| `/courses/{courseId}/next` | POST | ✅ | `courses.select_next_section()` | 2 hours |
| `/courses/{courseId}/standalone` | POST | ✅ | `courses.select_standalone_section()` | 2 hours |

#### Priority 2 - Enhanced Features

| Endpoint | Method | MAExpert | Complexity | Estimate |
|----------|--------|----------|------------|----------|
| `/courses/{courseId}/revise` | POST | ✅ | High (LLM) | 4 hours |
| `/courses/section/{sectionId}/audio` | GET | ✅ | Medium (TTS) | 3 hours |
| `/courses/section/{sectionId}/regenerate` | POST | ✅ | Medium | 3 hours |

#### Priority 3 - Advanced Features

- Lecture Q&A (`/section/{sectionId}/qa-question`)
- Audio streaming (`/section/{sectionId}/audio-stream`)
- Pause/resume Q&A modes

---

## Implementation Order

### Phase 1: Essential Course Management (Today)

**1. DELETE /courses/{courseId}** - 2-3 hours
- Create `course_delete` Lambda
- Implement cascading delete:
  - Delete section_deliveries (WHERE section_id IN course sections)
  - Delete course_sections (WHERE course_id = ?)
  - Delete course_state from DynamoDB
  - Delete course (WHERE course_id = ? AND user_id = ?)
- Wire to API Gateway
- Test with existing course

**2. POST /courses/{courseId}/next** - 2 hours
- Create `course_next_section` Lambda
- Reuse `select_next_section()` from `shared/logic/courses.py`
- Return section_id or null if complete
- Wire to API Gateway

**3. POST /courses/{courseId}/standalone** - 2 hours
- Create `course_standalone_section` Lambda  
- Reuse `select_standalone_section()` from `shared/logic/courses.py`
- Accept `time_available_minutes` parameter
- Return best matching section
- Wire to API Gateway

**Timeline:** ~6-7 hours for full course navigation

---

## DELETE Endpoint - Detailed Implementation

### MAExpert Reference

```python
@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course(
    course_id: str,
    current_user: UserResponse,
    db_client: PsycopgDatabaseClient,
):
    deleted = db_client.delete_course(course_id, current_user.user_id)
    if not deleted:
        raise HTTPException(404, "Course not found or no permission")
    return Response(status_code=204)
```

### Database Logic (from MAExpert)

```python
def delete_course(self, course_id: str, user_id: str) -> bool:
    """Delete course and all associated data (cascading)."""
    with self.get_connection() as conn:
        with conn.cursor() as cur:
            # 1. Delete lecture Q&A records
            cur.execute("""
                DELETE FROM lecture_qa_records
                WHERE section_id IN (
                    SELECT section_id FROM course_sections WHERE course_id = %s
                )
            """, (course_id,))
            
            # 2. Delete section deliveries
            cur.execute("""
                DELETE FROM section_deliveries
                WHERE section_id IN (
                    SELECT section_id FROM course_sections WHERE course_id = %s
                )
            """, (course_id,))
            
            # 3. Delete sections
            cur.execute("""
                DELETE FROM course_sections WHERE course_id = %s
            """, (course_id,))
            
            # 4. Delete course (with user_id check)
            cur.execute("""
                DELETE FROM courses
                WHERE course_id = %s AND user_id = %s
                RETURNING course_id
            """, (course_id, user_id))
            
            deleted = cur.fetchone() is not None
            conn.commit()
            return deleted
```

### AWS Implementation Plan

**File:** `src/lambda/course_delete/handler.py`

```python
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
    
    Cascading delete:
    1. section_deliveries (audio, lecture content)
    2. course_sections
    3. course_state (DynamoDB)
    4. courses (with user_id verification)
    """
    try:
        from shared.db_utils import get_db_connection
        from shared.response import success_response, error_response
        import boto3
        
        # Extract user_id from Cognito authorizer
        user_id = event.get('requestContext', {}).get('authorizer', {}).get('claims', {}).get('sub')
        if not user_id:
            return error_response(401, "Unauthorized - missing user_id")
        
        # Extract course_id from path
        course_id = event.get('pathParameters', {}).get('courseId')
        if not course_id:
            return error_response(400, "Missing courseId")
        
        logger.info(f"Deleting course {course_id} for user {user_id}")
        
        # Database cascading delete
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # 1. Delete section deliveries
                cur.execute("""
                    DELETE FROM section_deliveries
                    WHERE section_id IN (
                        SELECT section_id FROM course_sections WHERE course_id = %s
                    )
                """, (course_id,))
                deliveries_deleted = cur.rowcount
                logger.info(f"Deleted {deliveries_deleted} section deliveries")
                
                # 2. Delete course sections
                cur.execute("""
                    DELETE FROM course_sections WHERE course_id = %s
                    RETURNING section_id
                """, (course_id,))
                sections_deleted = cur.rowcount
                logger.info(f"Deleted {sections_deleted} course sections")
                
                # 3. Delete course (with user_id ownership check)
                cur.execute("""
                    DELETE FROM courses
                    WHERE course_id = %s AND user_id = %s
                    RETURNING course_id
                """, (course_id, user_id))
                
                deleted_course = cur.fetchone()
                if not deleted_course:
                    conn.rollback()
                    return error_response(404, "Course not found or you don't have permission to delete it")
                
                conn.commit()
        
        # 4. Delete course state from DynamoDB (best effort - don't fail if missing)
        try:
            dynamodb = boto3.resource('dynamodb')
            table_name = f"docprof-{os.getenv('ENVIRONMENT', 'dev')}-course-state"
            table = dynamodb.Table(table_name)
            table.delete_item(Key={'course_id': course_id})
            logger.info(f"Deleted course state from DynamoDB")
        except Exception as e:
            logger.warning(f"Could not delete DynamoDB state: {e}")
            # Don't fail - state cleanup is best-effort
        
        logger.info(f"Successfully deleted course {course_id}")
        
        # Return 204 No Content (success with no body)
        return {
            'statusCode': 204,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
        }
        
    except Exception as e:
        logger.error(f"Error deleting course: {e}", exc_info=True)
        return error_response(500, f"Failed to delete course: {str(e)}")
```

**Terraform:** `terraform/environments/dev/main.tf`
- Add `course_delete_lambda` module
- Wire to API Gateway `DELETE /courses/{courseId}`
- Grant RDS and DynamoDB permissions

---

## Next Steps

1. ✅ Implement DELETE endpoint (start now)
2. Implement POST /{courseId}/next
3. Implement POST /{courseId}/standalone
4. Test all three endpoints
5. Update frontend to use delete button

**Total time for Phase 1:** ~6-7 hours
