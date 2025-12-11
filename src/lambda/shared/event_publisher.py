"""
Event publisher for EventBridge course generation events.

Publishes events to EventBridge custom bus for course generation workflow.
"""

import json
import boto3
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

# Initialize EventBridge client
eventbridge = boto3.client('events')

# Event bus name (will be set by environment variable from Terraform)
import os
EVENT_BUS_NAME = os.getenv('EVENT_BUS_NAME', 'docprof-dev-course-events')
SOURCE = 'docprof.course'


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
            detail.update(data)
        
        if state_snapshot:
            detail['state_snapshot'] = state_snapshot
        
        response = eventbridge.put_events(
            Entries=[
                {
                    'Source': SOURCE,
                    'DetailType': event_type,
                    'Detail': json.dumps(detail),
                    'EventBusName': EVENT_BUS_NAME,
                }
            ]
        )
        
        if response['FailedEntryCount'] > 0:
            logger.error(f"Failed to publish event {event_type}: {response['Entries']}")
            raise Exception(f"EventBridge publish failed: {response['Entries']}")
        
        logger.info(f"Published event: {event_type} for course {course_id}")
        
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
