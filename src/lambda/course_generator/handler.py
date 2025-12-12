"""
Course generator Lambda - generates course outlines using multi-phase LLM approach.

Follows FP mapping strategy:
- Uses pure logic functions from shared/logic/courses.py
- Adapts effects to AWS services (Bedrock, Aurora, DynamoDB)
- Thin handler wrapper around logic layer

Course Generation Flow:
1. User requests course (query, hours, preferences)
2. Generate embedding for query
3. Search book summaries for relevant material
4. Phase 1: Generate course parts structure
5. Phase 2-N: Expand each part into sections
6. Phase N+1: Review and adjust for time accuracy
7. Store course outline in database
"""

import json
import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from uuid import uuid4

# Import shared utilities
from shared.bedrock_client import invoke_claude, generate_embeddings
from shared.db_utils import get_db_connection, vector_similarity_search
from shared.response import success_response, error_response

# Import course logic and models
from shared.logic.courses import (
    create_initial_course_state,
    reduce_course_event,
    request_course,
)
from shared.core.course_models import CoursePreferences, CourseState
from shared.core.course_events import (
    CourseRequestedEvent,
    EmbeddingGeneratedEvent,
    BookSummariesFoundEvent,
    PartsGeneratedEvent,
    PartSectionsGeneratedEvent,
    AllPartsCompleteEvent,
    OutlineReviewEvent,
    CourseStoredEvent,
)
from shared.core.commands import (
    LLMCommand,
    EmbedCommand,
    SearchBookSummariesCommand,
    CreateCourseCommand,
)
from shared.command_executor import execute_command

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for course generation requests.
    
    Expected event format (API Gateway):
    {
        "body": "{\"query\": \"Learn DCF valuation\", \"hours\": 2.0, \"preferences\": {...}}",
        "httpMethod": "POST",
        "path": "/courses",
        "headers": {...}
    }
    """
    try:
        # Parse request body
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})
        
        query = body.get('query')
        hours = body.get('hours', 2.0)
        preferences_dict = body.get('preferences', {})
        
        if not query:
            return error_response("Missing required field: query", status_code=400)
        
        # Convert preferences dict to CoursePreferences model
        preferences = CoursePreferences(**preferences_dict) if preferences_dict else CoursePreferences()
        
        # Create initial course state
        course_state = create_initial_course_state()
        course_state.session_id = str(uuid4())  # Generate session ID for this course generation
        
        # Create course request event
        course_event = CourseRequestedEvent(
            query=query,
            time_hours=float(hours),
            preferences=preferences
        )
        
        # Process course request through logic layer
        current_state = course_state
        current_result = reduce_course_event(current_state, course_event)
        current_state = current_result.new_state
        
        # Execute commands iteratively until pipeline completes
        max_iterations = 20  # Prevent infinite loops (increased for multi-phase generation)
        iteration = 0
        
        while current_result.commands and iteration < max_iterations:
            iteration += 1
            logger.info(f"Pipeline iteration {iteration}, executing {len(current_result.commands)} command(s)")
            
            # Execute first command and continue pipeline
            # (Commands are typically sequential, not parallel)
            command = current_result.commands[0]
            logger.info(f"Executing command: {command.command_name}")
            command_result = execute_command(command, state=current_state)
            
            # Handle command results and continue pipeline
            if isinstance(command, EmbedCommand):
                if command_result.get('status') == 'success' and 'embedding' in command_result:
                    embedding = command_result['embedding']
                    logger.info(f"Generated embedding (length: {len(embedding)})")
                    # Continue pipeline with embedding
                    embedding_event = EmbeddingGeneratedEvent(embedding=embedding)
                    current_result = reduce_course_event(current_state, embedding_event)
                    current_state = current_result.new_state
                else:
                    logger.error(f"Embedding generation failed: {command_result.get('error')}")
                    break
            
            elif isinstance(command, SearchBookSummariesCommand):
                if command_result.get('status') == 'success':
                    books = command_result.get('books', [])
                    logger.info(f"Found {len(books)} relevant books")
                    for book in books[:3]:  # Log first 3 books
                        logger.info(f"  - {book.get('book_title', 'Unknown')} (similarity: {book.get('similarity', 0):.3f})")
                    # Continue pipeline with book summaries
                    books_event = BookSummariesFoundEvent(books=books)
                    current_result = reduce_course_event(current_state, books_event)
                    current_state = current_result.new_state
                else:
                    logger.error(f"Book search failed: {command_result.get('error')}")
                    # Continue with empty books list
                    books_event = BookSummariesFoundEvent(books=[])
                    current_result = reduce_course_event(current_state, books_event)
                    current_state = current_result.new_state
            
            elif isinstance(command, LLMCommand):
                # Convert LLM command result to appropriate event based on task
                if command_result.get('status') == 'success' and 'content' in command_result:
                    content = command_result['content']
                    task = command.task or ''
                    
                    logger.info(f"LLM command executed successfully, task: {task}")
                    
                    # Convert LLM result to event based on task type
                    if task == 'generate_course_parts':
                        # Phase 1: Parts structure generated
                        event = PartsGeneratedEvent(parts_text=content)
                        logger.info("Converting LLM result to PartsGeneratedEvent")
                        current_result = reduce_course_event(current_state, event)
                        current_state = current_result.new_state
                        
                    elif task == 'generate_part_sections':
                        # Phase 2-N: Sections for a part generated
                        # Extract part_index from prompt_variables
                        part_index = command.prompt_variables.get('part_index', 0)
                        event = PartSectionsGeneratedEvent(
                            sections_text=content,
                            part_index=part_index
                        )
                        logger.info(f"Converting LLM result to PartSectionsGeneratedEvent (part_index={part_index})")
                        current_result = reduce_course_event(current_state, event)
                        current_state = current_result.new_state
                        
                    elif task == 'review_outline':
                        # Phase N+1: Outline review completed
                        event = OutlineReviewEvent(reviewed_outline_text=content)
                        logger.info("Converting LLM result to OutlineReviewEvent")
                        current_result = reduce_course_event(current_state, event)
                        current_state = current_result.new_state
                        
                    else:
                        # Unknown task - log warning but don't break
                        # Some LLM commands might not produce events (e.g., other use cases)
                        logger.warning(f"LLM command with unknown task '{task}' - no event conversion")
                        # Don't break - might be handled elsewhere or complete pipeline
                        
                else:
                    # LLM command failed
                    error_msg = command_result.get('error', 'Unknown error')
                    logger.error(f"LLM command failed: {error_msg}")
                    # Create error event to stop pipeline gracefully
                    from shared.core.course_events import CourseEventError
                    error_event = CourseEventError(error_message=error_msg)
                    current_result = reduce_course_event(current_state, error_event)
                    current_state = current_result.new_state
            
            elif isinstance(command, CreateCourseCommand):
                # Convert CreateCourseCommand result to CourseStoredEvent
                if command_result.get('status') == 'success':
                    course_id = command_result.get('course_id', '')
                    logger.info(f"Course created successfully: {course_id}")
                    event = CourseStoredEvent(course_id=course_id)
                    current_result = reduce_course_event(current_state, event)
                    current_state = current_result.new_state
                else:
                    error_msg = command_result.get('error', 'Failed to create course')
                    logger.error(f"Course creation failed: {error_msg}")
                    from shared.core.course_events import CourseEventError
                    error_event = CourseEventError(error_message=error_msg)
                    current_result = reduce_course_event(current_state, error_event)
                    current_state = current_result.new_state
            
            # If no new commands, pipeline is complete
            if not current_result.commands:
                logger.info("Pipeline complete - no more commands")
                break
        
        if iteration >= max_iterations:
            logger.warning(f"Pipeline reached max iterations ({max_iterations}), may be incomplete")
        
        # Return response
        return success_response({
            'session_id': course_state.session_id,
            'ui_message': current_result.ui_message,
            'iterations': iteration,
            'state': {
                'pending_course_query': current_state.pending_course_query,
                'pending_course_hours': current_state.pending_course_hours,
                'pending_book_search': current_state.pending_book_search if hasattr(current_state, 'pending_book_search') else False,
            }
        })
        
    except Exception as e:
        logger.error(f"Error in course generator: {e}", exc_info=True)
        return error_response(f"Internal server error: {str(e)}", status_code=500)
