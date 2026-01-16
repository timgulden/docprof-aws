"""
Course state manager - DynamoDB persistence for CourseState.

Handles serialization/deserialization of CourseState to/from DynamoDB,
preserving all fields and nested models.
"""

import os
import json
import boto3
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Dict, Any
import logging

from shared.core.course_models import (
    CourseState, CoursePreferences, Course, CourseSection,
    SectionDelivery, QASession
)

logger = logging.getLogger(__name__)

dynamodb = boto3.resource('dynamodb')
TABLE_NAME = os.getenv('DYNAMODB_COURSE_STATE_TABLE_NAME', 'docprof-dev-course-state')
STATE_TTL_SECONDS = 7 * 24 * 60 * 60  # 7 days


def get_table():
    """Get DynamoDB table for course state."""
    return dynamodb.Table(TABLE_NAME)


def _serialize_value(value: Any) -> Any:
    """
    Recursively serialize values for DynamoDB compatibility.
    Handles datetime, date, and other non-serializable types.
    """
    if isinstance(value, (datetime,)):
        return value.isoformat()
    elif isinstance(value, dict):
        return {k: _serialize_value(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_serialize_value(item) for item in value]
    elif isinstance(value, (int, float, str, bool, type(None))):
        return value
    else:
        # Try to convert to string as fallback
        try:
            return str(value)
        except Exception:
            return None


def course_state_to_dict(state: CourseState) -> Dict[str, Any]:
    """
    Convert CourseState to DynamoDB-compatible dict.
    
    Preserves ALL fields, including nested models.
    Uses model_dump() to ensure all fields are included.
    Converts float to Decimal for DynamoDB compatibility.
    """
    # Get all fields from Pydantic model
    state_dict = state.model_dump(mode='json')
    
    # Use session_id as course_id for DynamoDB key
    course_id = state.session_id or ''
    
    # Build DynamoDB item with all fields
    result = {
        'course_id': course_id,
        **state_dict,  # Include all CourseState fields
        'created_at': state.created_at.isoformat() if isinstance(state.created_at, datetime) else datetime.utcnow().isoformat(),
        'updated_at': state.updated_at.isoformat() if isinstance(state.updated_at, datetime) else datetime.utcnow().isoformat(),
        'ttl': int(datetime.now(timezone.utc).timestamp()) + STATE_TTL_SECONDS,
    }
    
    # Convert float to Decimal for DynamoDB compatibility
    if result.get('pending_course_hours') is not None and isinstance(result['pending_course_hours'], float):
        result['pending_course_hours'] = Decimal(str(result['pending_course_hours']))
    
    # Handle float fields in nested models
    if result.get('current_course') and isinstance(result['current_course'], dict):
        course = result['current_course']
        if course.get('estimated_hours') is not None and isinstance(course['estimated_hours'], float):
            course['estimated_hours'] = Decimal(str(course['estimated_hours']))
    
    if result.get('current_section') and isinstance(result['current_section'], dict):
        section = result['current_section']
        if section.get('estimated_minutes') is not None and isinstance(section['estimated_minutes'], (int, float)):
            section['estimated_minutes'] = int(section['estimated_minutes'])  # Keep as int
    
    # Handle nested models that need special serialization
    if state.pending_course_prefs:
        prefs_dict = state.pending_course_prefs.model_dump()
        result['pending_course_prefs'] = prefs_dict
    
    if state.current_course:
        course_dict = state.current_course.model_dump()
        # Convert float to Decimal
        if course_dict.get('estimated_hours') is not None and isinstance(course_dict['estimated_hours'], float):
            course_dict['estimated_hours'] = Decimal(str(course_dict['estimated_hours']))
        result['current_course'] = course_dict
    
    if state.current_section:
        section_dict = state.current_section.model_dump()
        # estimated_minutes is int, no conversion needed
        result['current_section'] = section_dict
    
    if state.current_delivery:
        delivery_dict = state.current_delivery.model_dump()
        # Convert float to Decimal if present
        if delivery_dict.get('duration_actual_minutes') is not None and isinstance(delivery_dict['duration_actual_minutes'], float):
            delivery_dict['duration_actual_minutes'] = int(delivery_dict['duration_actual_minutes'])
        result['current_delivery'] = delivery_dict
    
    if state.current_qa_session:
        qa_dict = state.current_qa_session.model_dump()
        result['current_qa_session'] = qa_dict
    
    # Handle Set type (pending_revision_completed_section_ids) - convert to list
    if state.pending_revision_completed_section_ids:
        result['pending_revision_completed_section_ids'] = list(state.pending_revision_completed_section_ids)
    
    # Serialize any remaining datetime objects recursively (handles nested datetimes)
    # This must be done LAST, after all other conversions
    result = _serialize_value(result)
    
    return result


def dict_to_course_state(state_dict: Dict[str, Any]) -> CourseState:
    """
    Convert DynamoDB dict to CourseState.
    
    Reconstructs all fields, including nested models.
    Preserves all CourseState fields exactly.
    Converts Decimal back to float for Pydantic compatibility.
    """
    # Extract course_id and use as session_id
    course_id = state_dict.pop('course_id', None)
    if course_id:
        state_dict['session_id'] = course_id
    
    # Remove DynamoDB-specific fields
    state_dict.pop('ttl', None)
    state_dict.pop('created_at', None)  # Will use model default
    state_dict.pop('updated_at', None)  # Will use model default
    
    # Convert Decimal back to float for Pydantic compatibility
    if state_dict.get('pending_course_hours') is not None:
        if isinstance(state_dict['pending_course_hours'], Decimal):
            state_dict['pending_course_hours'] = float(state_dict['pending_course_hours'])
    
    # Handle Decimal in nested models
    if state_dict.get('current_course') and isinstance(state_dict['current_course'], dict):
        course = state_dict['current_course']
        if course.get('estimated_hours') is not None and isinstance(course['estimated_hours'], Decimal):
            course['estimated_hours'] = float(course['estimated_hours'])
    
    # Handle nested models
    if 'pending_course_prefs' in state_dict and state_dict['pending_course_prefs']:
        state_dict['pending_course_prefs'] = CoursePreferences(**state_dict['pending_course_prefs'])
    
    if 'current_course' in state_dict and state_dict['current_course']:
        state_dict['current_course'] = Course(**state_dict['current_course'])
    
    if 'current_section' in state_dict and state_dict['current_section']:
        section_dict = state_dict['current_section']
        # Ensure required fields have defaults
        if 'estimated_minutes' not in section_dict:
            section_dict['estimated_minutes'] = 30  # Default
        state_dict['current_section'] = CourseSection(**section_dict)
    
    # Handle Set type conversion (list → set)
    if 'pending_revision_completed_section_ids' in state_dict:
        ids = state_dict['pending_revision_completed_section_ids']
        if isinstance(ids, list):
            state_dict['pending_revision_completed_section_ids'] = set(ids)
    
    # Create CourseState with all fields
    # Pydantic will handle defaults for missing fields
    return CourseState(**state_dict)


def load_course_state(course_id: str) -> Optional[CourseState]:
    """
    Load CourseState from DynamoDB.
    
    Returns None if course_id not found.
    """
    try:
        table = get_table()
        response = table.get_item(Key={'course_id': course_id})
        
        if 'Item' not in response:
            logger.warning(f"Course state not found: {course_id}")
            return None
        
        state_dict = response['Item']
        return dict_to_course_state(state_dict)
        
    except Exception as e:
        logger.error(f"Error loading course state {course_id}: {e}", exc_info=True)
        raise


def save_course_state(course_id: str, state: CourseState) -> None:
    """
    Save CourseState to DynamoDB.
    
    Creates or updates the state record.
    """
    try:
        table = get_table()
        state_dict = course_state_to_dict(state)
        
        # Ensure course_id matches
        state_dict['course_id'] = course_id
        
        table.put_item(Item=state_dict)
        logger.info(f"Saved course state: {course_id}")
        
    except Exception as e:
        logger.error(f"Error saving course state {course_id}: {e}", exc_info=True)
        raise


def update_course_state_status(course_id: str, status: str, error_message: Optional[str] = None) -> None:
    """
    Update course state status (for error tracking).
    
    Status values: "generating", "reviewing", "storing", "complete", "error"
    """
    try:
        table = get_table()
        update_expr = "SET #status = :status, updated_at = :updated_at"
        expr_attrs = {
            ':status': status,
            ':updated_at': datetime.utcnow().isoformat(),
        }
        expr_names = {'#status': 'status'}
        
        if error_message:
            update_expr += ", error_message = :error_message"
            expr_attrs[':error_message'] = error_message
        
        table.update_item(
            Key={'course_id': course_id},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_attrs,
            ExpressionAttributeNames=expr_names
        )
        
    except Exception as e:
        logger.error(f"Error updating course state status {course_id}: {e}", exc_info=True)
        raise


def delete_course_state(course_id: str) -> None:
    """
    Delete course state from DynamoDB.
    
    Used for cleanup after course is stored.
    """
    try:
        table = get_table()
        table.delete_item(Key={'course_id': course_id})
        logger.info(f"Deleted course state: {course_id}")
        
    except Exception as e:
        logger.error(f"Error deleting course state {course_id}: {e}", exc_info=True)
        raise
