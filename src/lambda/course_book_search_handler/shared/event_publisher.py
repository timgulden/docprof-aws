"""
Event publisher for EventBridge course generation events.

Publishes events to EventBridge custom bus for course generation workflow.
"""

import json
import boto3
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, date

logger = logging.getLogger(__name__)

# Initialize EventBridge client
eventbridge = boto3.client('events')

# Event bus name (will be set by environment variable from Terraform)
# Using default bus - set EVENT_BUS_NAME to empty string or omit to use default bus
import os
EVENT_BUS_NAME_ENV = os.getenv('EVENT_BUS_NAME', '').strip()
# Use default bus if EVENT_BUS_NAME is empty, None, or 'default'
EVENT_BUS_NAME = None if not EVENT_BUS_NAME_ENV or EVENT_BUS_NAME_ENV.lower() == 'default' else EVENT_BUS_NAME_ENV
SOURCE = 'docprof.course'


def _serialize_for_json(obj: Any) -> Any:
    """
    Recursively serialize objects for JSON encoding.
    Handles datetime, date, and other non-serializable types.
    """
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: _serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_serialize_for_json(item) for item in obj]
    elif isinstance(obj, (int, float, str, bool, type(None))):
        return obj
    else:
        # Try to convert to string as fallback
        try:
            return str(obj)
        except Exception:
            return None


def publish_course_event(
    event_type: str,
    course_id: str,
    data: Optional[Dict[str, Any]] = None,
    state_snapshot: Optional[Dict[str, Any]] = None
) -> None:
    """
    Publish a course generation event to EventBridge.
    
    Args:
        event_type: Event type (e.g., "CourseRequested", "PartsGenerated")
        course_id: Course ID (session_id)
        data: Event-specific data
        state_snapshot: Optional full state snapshot (for debugging)
    """
    try:
        detail = {
            'course_id': course_id,
            'timestamp': datetime.utcnow().isoformat(),
        }
        
        if data:
            # Serialize data to handle datetime objects
            serialized_data = _serialize_for_json(data)
            detail.update(serialized_data)
        
        if state_snapshot:
            detail['state_snapshot'] = _serialize_for_json(state_snapshot)
        
        event_entry = {
            'Source': SOURCE,
            'DetailType': event_type,
            'Detail': json.dumps(detail),
        }
        # Only include EventBusName if using a custom bus (not default)
        if EVENT_BUS_NAME:
            event_entry['EventBusName'] = EVENT_BUS_NAME
        
        bus_name_display = EVENT_BUS_NAME or 'default'
        logger.info(f"Publishing event to EventBridge: Source={SOURCE}, DetailType={event_type}, EventBusName={bus_name_display}")
        logger.debug(f"Event detail keys: {list(detail.keys())}")
        
        try:
            response = eventbridge.put_events(
                Entries=[event_entry]
            )
            
            logger.info(f"put_events response: FailedEntryCount={response.get('FailedEntryCount', 0)}, Entries={len(response.get('Entries', []))}")
            
            if response['FailedEntryCount'] > 0:
                error_details = response['Entries'][0] if response['Entries'] else {}
                logger.error(f"Failed to publish event {event_type}: {error_details}")
                raise Exception(f"EventBridge publish failed: {error_details}")
            
            event_id = response['Entries'][0].get('EventId', 'unknown') if response['Entries'] else 'unknown'
            logger.info(f"Published event: {event_type} for course {course_id}, EventId: {event_id}")
            
        except Exception as e:
            logger.error(f"Exception during put_events: {e}", exc_info=True)
            raise
        
    except Exception as e:
        logger.error(f"Error publishing event {event_type}: {e}", exc_info=True)
        raise


def publish_course_requested_event(course_id: str, query: str, hours: float, preferences: Dict[str, Any]) -> None:
    """Publish CourseRequestedEvent."""
    publish_course_event(
        event_type='CourseRequested',
        course_id=course_id,
        data={
            'query': query,
            'hours': hours,
            'preferences': preferences,
        }
    )


def publish_embedding_generated_event(course_id: str, embedding: List[float], task: Optional[str] = None) -> None:
    """Publish EmbeddingGeneratedEvent."""
    publish_course_event(
        event_type='EmbeddingGenerated',
        course_id=course_id,
        data={
            'embedding': embedding,
            'task': task,
        }
    )


def publish_book_summaries_found_event(course_id: str, books: List[Dict[str, Any]]) -> None:
    """Publish BookSummariesFoundEvent."""
    publish_course_event(
        event_type='BookSummariesFound',
        course_id=course_id,
        data={
            'books': books,
        }
    )


def publish_parts_generated_event(course_id: str, parts_text: str) -> None:
    """Publish PartsGeneratedEvent."""
    publish_course_event(
        event_type='PartsGenerated',
        course_id=course_id,
        data={
            'parts_text': parts_text,
        }
    )


def publish_part_sections_generated_event(course_id: str, sections_text: str, part_index: int) -> None:
    """Publish PartSectionsGeneratedEvent."""
    publish_course_event(
        event_type='PartSectionsGenerated',
        course_id=course_id,
        data={
            'sections_text': sections_text,
            'part_index': part_index,
        }
    )


def publish_all_parts_complete_event(course_id: str) -> None:
    """Publish AllPartsCompleteEvent (all parts expanded)."""
    publish_course_event(
        event_type='AllPartsComplete',
        course_id=course_id,
        data={}
    )


def publish_outline_reviewed_event(course_id: str, reviewed_outline_text: str) -> None:
    """Publish OutlineReviewedEvent."""
    publish_course_event(
        event_type='OutlineReviewed',
        course_id=course_id,
        data={
            'reviewed_outline_text': reviewed_outline_text,
        }
    )


def publish_course_stored_event(course_id: str, course_id_final: str) -> None:
    """Publish CourseStoredEvent."""
    publish_course_event(
        event_type='CourseStored',
        course_id=course_id,
        data={
            'course_id': course_id_final,  # Final course ID from database
        }
    )


def publish_course_error_event(course_id: str, error_message: str) -> None:
    """Publish CourseEventError."""
    publish_course_event(
        event_type='CourseEventError',
        course_id=course_id,
        data={
            'error_message': error_message,
        }
    )
