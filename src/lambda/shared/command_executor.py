"""
Command executor for course generation workflow.

Executes commands emitted by logic layer and returns results.
Preserves all command execution logic from MAExpert.
"""

import logging
from typing import Any, Dict, List, Optional

from shared.core.commands import (
    Command,
    EmbedCommand,
    LLMCommand,
    SearchBookSummariesCommand,
    SearchCorpusCommand,
    RetrieveChunksCommand,
    CreateCourseCommand,
    CreateSectionsCommand,
    StoreLectureCommand,
    GetBookTitlesCommand,
    ExtractTOCCommand,
    ExtractChapterTextCommand,
    StoreSourceSummaryCommand,
)
from shared.bedrock_client import invoke_claude, generate_embeddings
from shared.core.prompts import get_prompt
from shared.db_utils import get_db_connection, vector_similarity_search
import json
import uuid
from psycopg2.extras import execute_values

logger = logging.getLogger(__name__)


def execute_command(command: Command, state: Optional[Any] = None) -> Dict[str, Any]:
    """
    Execute a command and return result.
    
    Args:
        command: Command to execute
        state: Optional state context (for commands that need it)
    
    Returns:
        Dictionary with command execution result
    """
    if isinstance(command, EmbedCommand):
        return execute_embed_command(command)
    
    elif isinstance(command, LLMCommand):
        return execute_llm_command(command)
    
    elif isinstance(command, SearchBookSummariesCommand):
        return execute_search_book_summaries_command(command)
    
    elif isinstance(command, SearchCorpusCommand):
        return execute_search_corpus_command(command)
    
    elif isinstance(command, RetrieveChunksCommand):
        return execute_retrieve_chunks_command(command)
    
    elif isinstance(command, CreateCourseCommand):
        return execute_create_course_command(command)
    
    elif isinstance(command, CreateSectionsCommand):
        return execute_create_sections_command(command)
    
    elif isinstance(command, StoreLectureCommand):
        return execute_store_lecture_command(command)
    
    elif isinstance(command, GetBookTitlesCommand):
        return execute_get_book_titles_command(command)
    
    elif isinstance(command, ExtractTOCCommand):
        return execute_extract_toc_command(command)
    
    elif isinstance(command, ExtractChapterTextCommand):
        return execute_extract_chapter_text_command(command)
    
    elif isinstance(command, StoreSourceSummaryCommand):
        return execute_store_source_summary_command(command)
    
    else:
        logger.warning(f"Unhandled command type: {type(command).__name__}")
        return {'status': 'skipped', 'command_type': type(command).__name__}


def execute_embed_command(command: EmbedCommand) -> Dict[str, Any]:
    """Execute EmbedCommand - generate embedding for text."""
    try:
        # Generate embedding (returns list of embeddings)
        embeddings = generate_embeddings([command.text])
        
        if not embeddings or len(embeddings) == 0:
            raise ValueError("No embedding generated")
        
        embedding = embeddings[0]  # Single text → single embedding
        
        logger.info(f"Generated embedding for task: {command.task}")
        return {
            'status': 'success',
            'embedding': embedding,
            'task': command.task,
        }
        
    except Exception as e:
        logger.error(f"Error executing EmbedCommand: {e}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e),
            'task': command.task,
        }


def execute_llm_command(command: LLMCommand) -> Dict[str, Any]:
    """Execute LLMCommand - call Bedrock Claude."""
    try:
        # Get prompt text
        if command.prompt_name:
            # Use prompt registry
            prompt = get_prompt(command.prompt_name, command.prompt_variables)
        elif command.prompt:
            # Use inline prompt
            prompt = command.prompt
        else:
            raise ValueError("LLMCommand must have either prompt_name or prompt")
        
        # Call Claude
        response = invoke_claude(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=command.max_tokens,
            temperature=command.temperature,
            stream=False
        )
        
        content = response.get('content', '')
        usage = response.get('usage', {})
        
        logger.info(f"LLM response for task: {command.task}, tokens: {usage.get('input_tokens', 0) + usage.get('output_tokens', 0)}")
        
        return {
            'status': 'success',
            'content': content,
            'usage': usage,
            'task': command.task,
            'prompt_name': command.prompt_name,
        }
        
    except Exception as e:
        logger.error(f"Error executing LLMCommand: {e}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e),
            'task': command.task,
        }


def execute_search_book_summaries_command(command: SearchBookSummariesCommand) -> Dict[str, Any]:
    """
    Execute SearchBookSummariesCommand - search book summaries by embedding similarity.
    
    Searches the source_summaries table using vector similarity to find relevant books
    based on the user's query embedding.
    
    Returns books with their summary_json and similarity scores, ordered by relevance.
    """
    try:
        from shared.db_utils import get_db_connection
        from psycopg2.extras import RealDictCursor
        
        logger.info(f"Searching book summaries with top_k={command.top_k}, min_similarity={command.min_similarity}")
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Search source_summaries table using vector similarity
                # Get the latest version of each book's summary, then order by similarity
                # Join with books table to get book title
                cur.execute("""
                    WITH latest_summaries AS (
                        SELECT DISTINCT ON (book_id)
                            book_id,
                            summary_json,
                            embedding,
                            version,
                            generated_at
                        FROM source_summaries
                        WHERE embedding IS NOT NULL
                        ORDER BY book_id, version DESC
                    )
                    SELECT 
                        ls.book_id,
                        b.title as book_title,
                        ls.summary_json,
                        1 - (ls.embedding <=> %s::vector) as similarity,
                        ls.version,
                        ls.generated_at
                    FROM latest_summaries ls
                    INNER JOIN books b ON ls.book_id = b.book_id
                    WHERE 1 - (ls.embedding <=> %s::vector) >= %s
                    ORDER BY ls.embedding <=> %s::vector
                    LIMIT %s
                """, (
                    command.query_embedding,
                    command.query_embedding,
                    command.min_similarity,
                    command.query_embedding,
                    command.top_k
                ))
                
                results = cur.fetchall()
                books = [dict(row) for row in results]
                
                logger.info(f"Found {len(books)} relevant books")
                for book in books:
                    logger.info(f"  - {book.get('book_title', 'Unknown')} (similarity: {book.get('similarity', 0):.3f})")
                
                return {
                    'status': 'success',
                    'books': books,
                    'top_k': command.top_k,
                    'min_similarity': command.min_similarity,
                    'found': len(books),
                }
        
    except Exception as e:
        logger.error(f"Error executing SearchBookSummariesCommand: {e}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e),
            'books': [],
        }


def execute_search_corpus_command(command: SearchCorpusCommand) -> Dict[str, Any]:
    """Execute SearchCorpusCommand - search chunks by embedding similarity."""
    try:
        # Generate embedding for query
        embeddings = generate_embeddings([command.query_text])
        query_embedding = embeddings[0]
        
        # Search chunks
        results = vector_similarity_search(
            query_embedding=query_embedding,
            chunk_types=command.chunk_types,
            limit=sum(command.top_k.values()) if command.top_k else 10,
        )
        
        logger.info(f"Found {len(results)} chunks for corpus search")
        
        return {
            'status': 'success',
            'chunks': results,
            'query_text': command.query_text,
        }
        
    except Exception as e:
        logger.error(f"Error executing SearchCorpusCommand: {e}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e),
        }


def execute_retrieve_chunks_command(command: RetrieveChunksCommand) -> Dict[str, Any]:
    """Execute RetrieveChunksCommand - retrieve chunks by IDs."""
    try:
        # TODO: Implement chunk retrieval by IDs
        # This requires querying chunks table by chunk_id
        
        logger.warning("RetrieveChunksCommand not yet implemented")
        
        return {
            'status': 'success',
            'chunks': [],  # Empty until implemented
            'chunk_ids': command.chunk_ids,
        }
        
    except Exception as e:
        logger.error(f"Error executing RetrieveChunksCommand: {e}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e),
        }


def execute_create_course_command(command: CreateCourseCommand) -> Dict[str, Any]:
    """Execute CreateCourseCommand - store course in database."""
    try:
        course = command.course
        
        # Keep UUIDs as strings - PostgreSQL will cast them with ::uuid
        course_id = course.course_id
        user_id = course.user_id
        
        # Convert preferences to JSONB
        preferences_json = json.dumps(course.preferences.model_dump())
        
        # Convert datetime objects to ISO strings for PostgreSQL
        from datetime import datetime
        created_at = course.created_at.isoformat() if isinstance(course.created_at, datetime) else course.created_at
        last_modified = course.last_modified.isoformat() if isinstance(course.last_modified, datetime) else course.last_modified
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO courses (
                        course_id, user_id, title, original_query,
                        estimated_hours, created_at, last_modified,
                        preferences, status
                    )
                    VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s::timestamp, %s::timestamp, %s::jsonb, %s)
                    ON CONFLICT (course_id) DO UPDATE SET
                        title = EXCLUDED.title,
                        original_query = EXCLUDED.original_query,
                        estimated_hours = EXCLUDED.estimated_hours,
                        last_modified = EXCLUDED.last_modified,
                        preferences = EXCLUDED.preferences,
                        status = EXCLUDED.status
                    RETURNING course_id
                    """,
                    (
                        course_id,
                        user_id,
                        course.title,
                        course.original_query,
                        course.estimated_hours,
                        created_at,
                        last_modified,
                        preferences_json,
                        course.status,
                    )
                )
                stored_course_id = str(cur.fetchone()[0])
        
        logger.info(f"Course stored successfully: {stored_course_id}")
        
        return {
            'status': 'success',
            'course_id': stored_course_id,
            'course': course.model_dump(),
        }
        
    except Exception as e:
        logger.error(f"Error executing CreateCourseCommand: {e}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e),
        }


def execute_create_sections_command(command: CreateSectionsCommand) -> Dict[str, Any]:
    """Execute CreateSectionsCommand - store sections in database."""
    try:
        sections = command.sections
        
        if not sections:
            logger.warning("CreateSectionsCommand called with empty sections list")
            return {
                'status': 'success',
                'sections_count': 0,
                'sections': [],
            }
        
        # Prepare batch insert data
        values = []
        for section in sections:
            # Keep UUIDs as strings - psycopg2 will handle conversion
            section_id = section.section_id
            course_id = section.course_id
            parent_section_id = section.parent_section_id if section.parent_section_id else None
            
            # Keep chunk_ids and prerequisites as string arrays - PostgreSQL will cast them
            chunk_ids_array = section.chunk_ids if section.chunk_ids else []
            prerequisites_array = section.prerequisites if section.prerequisites else []
            
            # Convert learning_objectives to TEXT array
            learning_objectives_array = section.learning_objectives if section.learning_objectives else []
            
            values.append((
                section_id,  # Will be cast to UUID by PostgreSQL
                course_id,  # Will be cast to UUID by PostgreSQL
                parent_section_id,  # Will be cast to UUID by PostgreSQL (or NULL)
                section.order_index,
                section.title,
                learning_objectives_array,  # TEXT[]
                section.content_summary,
                section.estimated_minutes,
                chunk_ids_array,  # Will be cast to UUID[] by PostgreSQL
                section.status,
                section.completed_at.isoformat() if section.completed_at else None,  # Convert datetime to ISO string
                section.can_standalone,
                prerequisites_array,  # Will be cast to UUID[] by PostgreSQL
                section.created_at.isoformat() if section.created_at else None,  # Convert datetime to ISO string
            ))
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Batch insert sections
                # Convert datetime objects to ISO strings for PostgreSQL
                from datetime import datetime
                serialized_values = []
                for val_tuple in values:
                    serialized_tuple = []
                    for i, val in enumerate(val_tuple):
                        if isinstance(val, datetime):
                            serialized_tuple.append(val.isoformat())
                        else:
                            serialized_tuple.append(val)
                    serialized_values.append(tuple(serialized_tuple))
                
                execute_values(
                    cur,
                    """
                    INSERT INTO course_sections (
                        section_id, course_id, parent_section_id, order_index,
                        title, learning_objectives, content_summary,
                        estimated_minutes, chunk_ids, status,
                        completed_at, can_standalone, prerequisites, created_at
                    )
                    VALUES %s
                    ON CONFLICT (section_id) DO UPDATE SET
                        course_id = EXCLUDED.course_id,
                        parent_section_id = EXCLUDED.parent_section_id,
                        order_index = EXCLUDED.order_index,
                        title = EXCLUDED.title,
                        learning_objectives = EXCLUDED.learning_objectives,
                        content_summary = EXCLUDED.content_summary,
                        estimated_minutes = EXCLUDED.estimated_minutes,
                        chunk_ids = EXCLUDED.chunk_ids,
                        status = EXCLUDED.status,
                        completed_at = EXCLUDED.completed_at,
                        can_standalone = EXCLUDED.can_standalone,
                        prerequisites = EXCLUDED.prerequisites
                    """,
                    values,
                    template="""(
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )"""
                )
        
        logger.info(f"Stored {len(sections)} sections successfully for course {sections[0].course_id}")
        
        return {
            'status': 'success',
            'sections_count': len(sections),
            'sections': [s.model_dump() for s in sections],
        }
        
    except Exception as e:
        logger.error(f"Error executing CreateSectionsCommand: {e}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e),
        }


def execute_store_lecture_command(command: StoreLectureCommand) -> Dict[str, Any]:
    """Execute StoreLectureCommand - store lecture delivery."""
    try:
        # TODO: Implement lecture storage
        # This requires:
        # 1. section_deliveries table
        # 2. Insert delivery record
        
        logger.warning("StoreLectureCommand not yet implemented")
        
        return {
            'status': 'success',
            'delivery_id': command.delivery.delivery_id,
            'section_id': command.delivery.section_id,
        }
        
    except Exception as e:
        logger.error(f"Error executing StoreLectureCommand: {e}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e),
        }


def execute_get_book_titles_command(command: GetBookTitlesCommand) -> Dict[str, Any]:
    """Execute GetBookTitlesCommand - lookup book titles by IDs."""
    try:
        # TODO: Implement book title lookup
        # This requires querying books table by book_id
        
        logger.warning("GetBookTitlesCommand not yet implemented")
        
        return {
            'status': 'success',
            'book_titles': {},  # Empty until implemented
            'book_ids': command.book_ids,
        }
        
    except Exception as e:
        logger.error(f"Error executing GetBookTitlesCommand: {e}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e),
        }


def execute_extract_toc_command(command: ExtractTOCCommand) -> Dict[str, Any]:
    """
    Execute ExtractTOCCommand - extract TOC from PDF in S3.
    
    Uses PyMuPDF to extract table of contents from PDF.
    """
    try:
        import boto3
        import fitz  # PyMuPDF
        
        s3_client = boto3.client('s3')
        
        # Download PDF from S3
        logger.info(f"Downloading PDF from s3://{command.s3_bucket}/{command.s3_key}")
        pdf_response = s3_client.get_object(Bucket=command.s3_bucket, Key=command.s3_key)
        pdf_data = pdf_response['Body'].read()
        
        # Extract TOC using PyMuPDF
        doc = fitz.open(stream=pdf_data, filetype="pdf")
        toc_raw = doc.get_toc()  # Returns list of (level, title, page) tuples
        
        # Get metadata
        metadata = doc.metadata
        source_title = metadata.get('title', 'Unknown')
        author = metadata.get('author', 'Unknown')
        total_pages = len(doc)
        
        doc.close()
        
        logger.info(f"Extracted TOC: {len(toc_raw)} entries, {total_pages} pages")
        
        return {
            'status': 'success',
            'toc_raw': toc_raw,
            'source_title': source_title,
            'author': author,
            'total_pages': total_pages,
        }
        
    except Exception as e:
        logger.error(f"Error executing ExtractTOCCommand: {e}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e),
        }


def execute_extract_chapter_text_command(command: ExtractChapterTextCommand) -> Dict[str, Any]:
    """
    Execute ExtractChapterTextCommand - extract text for specific chapter from PDF in S3.
    """
    try:
        import boto3
        import fitz  # PyMuPDF
        
        s3_client = boto3.client('s3')
        
        # Download PDF from S3
        logger.info(f"Downloading PDF from s3://{command.s3_bucket}/{command.s3_key} for pages {command.start_page}-{command.end_page}")
        pdf_response = s3_client.get_object(Bucket=command.s3_bucket, Key=command.s3_key)
        pdf_data = pdf_response['Body'].read()
        
        # Extract text from page range
        doc = fitz.open(stream=pdf_data, filetype="pdf")
        chapter_text_parts = []
        
        # PyMuPDF uses 0-based indexing, but TOC uses 1-based
        for page_num in range(command.start_page - 1, min(command.end_page, len(doc))):
            page = doc[page_num]
            chapter_text_parts.append(page.get_text())
        
        chapter_text = "\n".join(chapter_text_parts)
        doc.close()
        
        logger.info(f"Extracted {len(chapter_text)} characters from pages {command.start_page}-{command.end_page}")
        
        return {
            'status': 'success',
            'chapter_text': chapter_text,
            'chapter_title': command.chapter_title,
            'start_page': command.start_page,
            'end_page': command.end_page,
        }
        
    except Exception as e:
        logger.error(f"Error executing ExtractChapterTextCommand: {e}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e),
        }


def execute_store_source_summary_command(command: StoreSourceSummaryCommand) -> Dict[str, Any]:
    """
    Execute StoreSourceSummaryCommand - store source summary in database.
    """
    try:
        from shared.db_utils import get_db_connection
        from psycopg2.extras import RealDictCursor
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Store summary in source_summaries table
                # Convert source_id to UUID if it's a string
                import uuid
                try:
                    book_id_uuid = uuid.UUID(command.source_id) if isinstance(command.source_id, str) else command.source_id
                except (ValueError, AttributeError):
                    logger.error(f"Invalid UUID format for source_id: {command.source_id}")
                    raise ValueError(f"Invalid UUID format: {command.source_id}")
                
                cur.execute("""
                    INSERT INTO source_summaries (
                        book_id, summary_json, generated_by, version
                    )
                    VALUES (%s::uuid, %s::jsonb, %s, 1)
                    ON CONFLICT (book_id, version) 
                    DO UPDATE SET
                        summary_json = EXCLUDED.summary_json,
                        generated_at = NOW(),
                        generated_by = EXCLUDED.generated_by
                    RETURNING summary_id
                """, (
                    str(book_id_uuid),  # Ensure it's a string for psycopg2
                    command.summary_json,
                    'claude-sonnet-4-5-bedrock',  # Generated by
                ))
                
                summary_id = str(cur.fetchone()['summary_id'])
                conn.commit()
                
                logger.info(f"Stored source summary: {summary_id} for source_id: {command.source_id}")
                
                return {
                    'status': 'success',
                    'summary_id': summary_id,
                    'source_id': command.source_id,
                }
        
    except Exception as e:
        logger.error(f"Error executing StoreSourceSummaryCommand: {e}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e),
        }
