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
        model_used = response.get('model_used', 'unknown')
        model_switched = response.get('model_switched', False)
        
        logger.info(f"LLM response for task: {command.task}, tokens: {usage.get('input_tokens', 0) + usage.get('output_tokens', 0)}, model: {model_used}")
        
        result = {
            'status': 'success',
            'content': content,
            'usage': usage,
            'task': command.task,
            'prompt_name': command.prompt_name,
            'model_used': model_used,
        }
        
        # If model was switched, add notification info
        if model_switched:
            primary_model = response.get('primary_model', 'primary')
            fallback_model = response.get('fallback_model', 'fallback')
            logger.warning(
                f"Model switched from {primary_model} to {fallback_model} "
                f"due to daily token limit (task: {command.task})"
            )
            result['model_switched'] = True
            result['model_switch_notification'] = (
                f"Note: Using backup model ({fallback_model}) because the primary model "
                f"({primary_model}) has reached its daily token limit. "
                f"Quality may vary slightly."
            )
        
        return result
        
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
    
    UPDATED APPROACH: Instead of requiring a single book-level embedding (which hits
    Titan's 8k token limit for large books), we search the chunks table and group by
    book_id. This finds books that have relevant content chunks, which is more accurate
    and doesn't require truncation.
    
    Returns books with their summary_json and similarity scores, ordered by relevance.
    """
    try:
        from shared.db_utils import get_db_connection
        from psycopg2.extras import RealDictCursor
        
        logger.info(f"Searching books via chunks with top_k={command.top_k}, min_similarity={command.min_similarity}")
        logger.info(f"Query embedding length: {len(command.query_embedding) if command.query_embedding else 'None'}")
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # First, check if we have any chunks with embeddings at all
                cur.execute("SELECT COUNT(*) as total, COUNT(embedding) as with_embedding FROM chunks")
                chunk_stats = cur.fetchone()
                logger.info(f"Database stats: {chunk_stats[0]} total chunks, {chunk_stats[1]} with embeddings")
                
                # NEW APPROACH: Search chunks, group by book, then join with source_summaries
                # This avoids the token limit issue and is more accurate (searches actual content, not just summary)
                logger.info(f"Executing chunk search query with min_similarity={command.min_similarity}")
                cur.execute("""
                    WITH relevant_chunks AS (
                        -- Find chunks that match the query (top 50 to ensure we sample from multiple books)
                        SELECT 
                            book_id,
                            1 - (embedding <=> %s::vector) as similarity
                        FROM chunks
                        WHERE embedding IS NOT NULL
                          AND 1 - (embedding <=> %s::vector) >= %s
                        ORDER BY embedding <=> %s::vector
                        LIMIT 50
                    ),
                    book_relevance AS (
                        -- Group by book and take the best similarity score per book
                        SELECT 
                            book_id,
                            MAX(similarity) as max_similarity,
                            COUNT(*) as matching_chunks
                        FROM relevant_chunks
                        GROUP BY book_id
                    )
                    SELECT 
                        br.book_id,
                        b.title as book_title,
                        ss.summary_json,
                        br.max_similarity as similarity,
                        br.matching_chunks,
                        ss.version,
                        ss.generated_at
                    FROM book_relevance br
                    INNER JOIN books b ON br.book_id = b.book_id
                    LEFT JOIN LATERAL (
                        SELECT summary_json, version, generated_at
                        FROM source_summaries
                        WHERE book_id = br.book_id
                        ORDER BY version DESC
                        LIMIT 1
                    ) ss ON true
                    ORDER BY br.max_similarity DESC
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
                
                # Check how many chunks matched before grouping
                cur.execute("""
                    SELECT COUNT(*) as matching_count
                    FROM chunks
                    WHERE embedding IS NOT NULL
                      AND 1 - (embedding <=> %s::vector) >= %s
                """, (command.query_embedding, command.min_similarity))
                matching_chunks_count = cur.fetchone()[0]
                logger.info(f"Found {matching_chunks_count} chunks matching threshold (before grouping)")
                
                logger.info(f"Found {len(books)} relevant books (via chunk search)")
                if len(books) == 0:
                    logger.warning(f"No books found! This could mean:")
                    logger.warning(f"  1. No chunks have embeddings (checked: {chunk_stats[1]} chunks have embeddings)")
                    logger.warning(f"  2. Similarity threshold {command.min_similarity} is too high ({matching_chunks_count} chunks matched)")
                    logger.warning(f"  3. Query embedding doesn't match any content")
                for book in books:
                    logger.info(
                        f"  - {book.get('book_title', 'Unknown')} "
                        f"(similarity: {book.get('similarity', 0):.3f}, "
                        f"{book.get('matching_chunks', 0)} matching chunks)"
                    )
                
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
    """Execute RetrieveChunksCommand - retrieve chunks by IDs from database."""
    try:
        chunk_ids = command.chunk_ids
        
        if not chunk_ids:
            logger.warning("RetrieveChunksCommand called with empty chunk_ids")
            return {
                'status': 'success',
                'chunks': [],
                'chunk_ids': [],
            }
        
        logger.info(f"Retrieving {len(chunk_ids)} chunks from database")
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Query chunks by IDs
                # Use ANY to match multiple UUIDs
                cur.execute("""
                    SELECT 
                        c.chunk_id,
                        c.book_id,
                        c.chunk_type,
                        c.content,
                        c.page_start,
                        c.page_end,
                        c.chapter_number,
                        c.chapter_title,
                        b.title as book_title,
                        b.author as book_author
                    FROM chunks c
                    LEFT JOIN books b ON c.book_id = b.book_id
                    WHERE c.chunk_id = ANY(%s::uuid[])
                    ORDER BY c.page_start
                """, (chunk_ids,))
                
                rows = cur.fetchall()
                
                # Format chunks as dicts
                chunks = []
                for row in rows:
                    (chunk_id, book_id, chunk_type, content, page_start, page_end,
                     chapter_number, chapter_title, book_title, book_author) = row
                    
                    chunks.append({
                        'chunk_id': str(chunk_id),
                        'book_id': str(book_id),
                        'chunk_type': chunk_type,
                        'content': content,
                        'page_start': page_start,
                        'page_end': page_end,
                        'chapter_number': chapter_number,
                        'chapter_title': chapter_title,
                        'book_title': book_title,
                        'book_author': book_author,
                    })
                
                logger.info(f"✓ Retrieved {len(chunks)} chunks")
        
        return {
            'status': 'success',
            'chunks': chunks,
            'chunk_ids': chunk_ids,
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
        
        logger.info(f"execute_create_sections_command: Starting execution with {len(sections)} sections")
        if not sections:
            logger.error("CRITICAL: CreateSectionsCommand called with empty sections list!")
            return {
                'status': 'error',
                'error': 'Empty sections list - no sections to store',
                'sections_count': 0,
                'sections': [],
            }
        
        if sections:
            logger.info(f"execute_create_sections_command: First section: course_id={sections[0].course_id}, title='{sections[0].title[:50]}', order_index={sections[0].order_index}")
            logger.info(f"execute_create_sections_command: Last section: course_id={sections[-1].course_id}, title='{sections[-1].title[:50]}', order_index={sections[-1].order_index}")
            logger.info(f"execute_create_sections_command: Total sections: {len(sections)}, Total estimated minutes: {sum(s.estimated_minutes for s in sections)}")
        
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
                
                logger.info(f"execute_create_sections_command: Executing batch insert of {len(values)} sections")
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
                
                # Verify sections were actually inserted
                cur.execute(
                    "SELECT COUNT(*) FROM course_sections WHERE course_id = %s::uuid",
                    (sections[0].course_id,)
                )
                stored_count = cur.fetchone()[0]
                logger.info(f"execute_create_sections_command: Verified {stored_count} sections in database for course {sections[0].course_id}")
                
                if stored_count == 0:
                    logger.error(f"CRITICAL: No sections found in database after insert! Expected {len(sections)} sections.")
        
        logger.info(f"execute_create_sections_command: Successfully stored {len(sections)} sections for course {sections[0].course_id}")
        
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
    """Execute StoreLectureCommand - store lecture delivery to database."""
    try:
        delivery = command.delivery
        
        logger.info(f"Storing lecture for section {delivery.section_id}")
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Insert or update section delivery
                cur.execute("""
                    INSERT INTO section_deliveries (
                        delivery_id, section_id, user_id, lecture_script,
                        delivered_at, duration_actual_minutes, user_notes, style_snapshot
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (delivery_id) DO UPDATE SET
                        lecture_script = EXCLUDED.lecture_script,
                        delivered_at = EXCLUDED.delivered_at,
                        duration_actual_minutes = EXCLUDED.duration_actual_minutes,
                        user_notes = EXCLUDED.user_notes,
                        style_snapshot = EXCLUDED.style_snapshot
                    RETURNING delivery_id
                """, (
                    delivery.delivery_id,
                    delivery.section_id,
                    delivery.user_id,
                    delivery.lecture_script,
                    delivery.delivered_at,
                    delivery.duration_actual_minutes,
                    delivery.user_notes,
                    json.dumps(delivery.style_snapshot) if delivery.style_snapshot else '{}'
                ))
                delivery_id = cur.fetchone()[0]
                conn.commit()
                
                logger.info(f"✓ Lecture stored with delivery_id: {delivery_id}")
        
        return {
            'status': 'success',
            'delivery_id': str(delivery_id),
            'section_id': delivery.section_id,
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


"""
Clean TOC extraction implementation - following Lambda best practices.
Single responsibility functions, no silent fallbacks.
"""

from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


def _extract_pdf_metadata(pdf_bytes: bytes) -> Dict[str, Any]:
    """
    Extract metadata and page text from PDF.
    Single responsibility: PDF parsing only.
    
    Returns:
        Dict with source_title, author, total_pages, pages_text
    """
    import fitz
    
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    
    # Get metadata
    metadata = doc.metadata
    source_title = metadata.get('title', 'Unknown')
    author = metadata.get('author', 'Unknown')
    total_pages = len(doc)
    
    # Extract page text for LLM extraction
    pages_text = []
    for page_num in range(len(doc)):
        try:
            page = doc[page_num]
            pages_text.append(page.get_text("text"))
        except Exception as e:
            logger.warning(f"Failed to extract text from page {page_num + 1}: {e}")
            pages_text.append("")
    
    doc.close()
    
    logger.info(f"Extracted metadata: {total_pages} pages, title: {source_title}")
    
    return {
        'source_title': source_title,
        'author': author,
        'total_pages': total_pages,
        'pages_text': pages_text,
    }


def _extract_chapters_with_dual_path(
    pdf_bytes: bytes,
    pages_text: List[str],
    source_title: str,
) -> Optional[List]:
    """
    Extract chapters using dual-path: hyperlink first (fast), visual if needed (comprehensive).
    Single responsibility: Chapter extraction orchestration.
    
    No fallbacks - fails explicitly if both paths fail.
    
    Returns:
        List of ChapterRange objects, or None if extraction fails
    """
    from shared.toc_parser_llm import (
        find_toc,
        extract_chapters_from_hyperlinks,
        identify_chapter_ranges,
    )
    
    # Step 1: Find TOC pages (1 LLM call, ~$0.01)
    logger.info("Finding TOC pages using LLM vision")
    toc_pages = find_toc(
        pdf_bytes=pdf_bytes,
        pages=pages_text,
        book_title=source_title,
    )
    
    if not toc_pages:
        logger.error("Could not find TOC pages in PDF")
        return None
    
    logger.info(f"Found TOC at pages {toc_pages[0]}-{toc_pages[1]}")
    
    # Step 2: Try hyperlink extraction (fast, free - just parses hyperlinks)
    logger.info("Extracting chapters from hyperlinks")
    hyperlink_chapters = None
    try:
        hyperlink_chapters = extract_chapters_from_hyperlinks(
            pdf_bytes=pdf_bytes,
            toc_pages=toc_pages,
            book_title=source_title,
        )
        if hyperlink_chapters:
            logger.info(f"Hyperlink extraction found {len(hyperlink_chapters)} chapters")
        else:
            logger.warning("Hyperlink extraction returned no chapters")
    except Exception as e:
        logger.error(f"Hyperlink extraction failed: {e}", exc_info=True)
    
    # Step 3: If hyperlink insufficient OR we want to verify/enhance, try visual extraction
    # For now, always try visual to ensure we find all chapters
    visual_chapters = None
    if not hyperlink_chapters or len(hyperlink_chapters) < 50:  # Increased threshold to always run for Valuation
        logger.info(
            f"Hyperlink extraction insufficient ({len(hyperlink_chapters) if hyperlink_chapters else 0} chapters), "
            f"trying visual/LLM extraction"
        )
        try:
            visual_chapters = identify_chapter_ranges(
                pdf_bytes=pdf_bytes,
                toc_pages=toc_pages,
                pages=pages_text,
                book_title=source_title,
            )
            if visual_chapters:
                logger.info(f"Visual extraction found {len(visual_chapters)} chapters")
            else:
                logger.warning("Visual extraction returned no chapters")
        except Exception as e:
            logger.error(f"Visual extraction failed: {e}", exc_info=True)
    
    # Step 4: Use best result (fail explicitly if both failed)
    if hyperlink_chapters and visual_chapters:
        if len(visual_chapters) > len(hyperlink_chapters):
            logger.info(
                f"Using visual results ({len(visual_chapters)} chapters) "
                f"over hyperlink ({len(hyperlink_chapters)} chapters)"
            )
            return visual_chapters
        else:
            logger.info(
                f"Using hyperlink results ({len(hyperlink_chapters)} chapters) "
                f"over visual ({len(visual_chapters) if visual_chapters else 0} chapters)"
            )
            return hyperlink_chapters
    elif visual_chapters:
        logger.info(f"Using visual results ({len(visual_chapters)} chapters)")
        return visual_chapters
    elif hyperlink_chapters:
        logger.info(f"Using hyperlink results ({len(hyperlink_chapters)} chapters)")
        return hyperlink_chapters
    else:
        logger.error("Both hyperlink and visual extraction failed - no chapters extracted")
        return None


def execute_extract_toc_command(command: ExtractTOCCommand) -> Dict[str, Any]:
    """
    Execute ExtractTOCCommand - always uses LLM extraction for consistent, reliable results.
    
    Strategy (no fallbacks):
    1. Extract PDF metadata and text
    2. Use dual-path extraction (hyperlink → visual if needed)
    3. Convert chapters to toc_raw format (all Level 1 for simple parsing)
    4. Fail explicitly if extraction fails
    
    This approach ensures consistent results and avoids silent degradation.
    Following Lambda best practices: single responsibility, explicit failures.
    """
    try:
        import boto3
        from shared.toc_parser_llm import convert_chapter_ranges_to_toc_raw
        
        s3_client = boto3.client('s3')
        
        # Download PDF from S3
        logger.info(f"Downloading PDF from s3://{command.s3_bucket}/{command.s3_key}")
        pdf_response = s3_client.get_object(Bucket=command.s3_bucket, Key=command.s3_key)
        pdf_data = pdf_response['Body'].read()
        
        # Extract metadata and text (single responsibility)
        metadata = _extract_pdf_metadata(pdf_data)
        source_title = metadata['source_title']
        author = metadata['author']
        total_pages = metadata['total_pages']
        pages_text = metadata['pages_text']
        
        # Always use LLM extraction - no PyMuPDF fallback (explicit over implicit)
        logger.info("Using LLM-based chapter extraction (hyperlink → visual)")
        chapters = _extract_chapters_with_dual_path(
            pdf_bytes=pdf_data,
            pages_text=pages_text,
            source_title=source_title,
        )
        
        # Fail explicitly - no silent fallback
        if not chapters:
            return {
                'status': 'error',
                'error': 'TOC extraction failed - could not extract chapters using hyperlink or visual methods',
            }
        
        # Convert to toc_raw format (all Level 1 for simple parsing)
        logger.info(f"Converting {len(chapters)} chapters to toc_raw format")
        page_offset = 0
        if chapters and chapters[0].start_page:
            # Rough offset estimate (book pages vs PDF pages)
            page_offset = max(0, chapters[0].start_page - 50)
        
        toc_raw = convert_chapter_ranges_to_toc_raw(
            chapters,
            page_offset=page_offset,
        )
        
        logger.info(f"Successfully extracted {len(toc_raw)} chapters for: {source_title}")
        
        return {
            'status': 'success',
            'toc_raw': toc_raw,
            'source_title': source_title,
            'author': author,
            'total_pages': total_pages,
            # No identified_chapter_level - all entries are Level 1, simple parsing
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
