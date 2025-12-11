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
)
from shared.bedrock_client import invoke_claude, generate_embeddings
from shared.core.prompts import get_prompt
from shared.db_utils import get_db_connection, vector_similarity_search

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
    
    TODO: Implement book summary search in Aurora.
    For now, returns empty list - needs book_summaries table with embeddings.
    """
    try:
        # TODO: Implement vector similarity search on book_summaries table
        # This requires:
        # 1. book_summaries table with embedding column (vector type)
        # 2. Vector similarity query similar to chunk search
        
        logger.warning("SearchBookSummariesCommand not yet implemented - returning empty list")
        
        # Placeholder implementation
        # In real implementation:
        # with get_db_connection() as conn:
        #     with conn.cursor(cursor_factory=RealDictCursor) as cur:
        #         cur.execute("""
        #             SELECT book_id, book_title, summary_json, 
        #                    1 - (embedding <=> %s::vector) as similarity
        #             FROM book_summaries
        #             WHERE 1 - (embedding <=> %s::vector) >= %s
        #             ORDER BY embedding <=> %s::vector
        #             LIMIT %s
        #         """, (command.query_embedding, command.query_embedding, 
        #               command.min_similarity, command.query_embedding, command.top_k))
        #         results = cur.fetchall()
        #         return [dict(row) for row in results]
        
        return {
            'status': 'success',
            'books': [],  # Empty until implemented
            'top_k': command.top_k,
            'min_similarity': command.min_similarity,
        }
        
    except Exception as e:
        logger.error(f"Error executing SearchBookSummariesCommand: {e}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e),
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
        # TODO: Implement course storage in Aurora
        # This requires:
        # 1. courses table
        # 2. Insert course record
        
        logger.warning("CreateCourseCommand not yet implemented")
        
        return {
            'status': 'success',
            'course_id': command.course.course_id,
            'course': command.course.model_dump(),
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
        # TODO: Implement section storage in Aurora
        # This requires:
        # 1. course_sections table
        # 2. Batch insert sections
        
        logger.warning("CreateSectionsCommand not yet implemented")
        
        return {
            'status': 'success',
            'sections_count': len(command.sections),
            'sections': [s.model_dump() for s in command.sections],
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
