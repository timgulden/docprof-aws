"""
Effects Adapter Layer
Maps MAExpert effect signatures to AWS service implementations
This allows direct reuse of MAExpert logic functions
"""

import os
import logging
from typing import Dict, List, Any, Callable, Optional
from functools import partial

from .bedrock_client import generate_embeddings, invoke_claude, describe_figure
from .db_utils import (
    get_db_connection,
    vector_similarity_search,
    insert_chunks_batch,
    insert_book,
    insert_figures_batch
)

logger = logging.getLogger(__name__)


def create_effects_adapter() -> Dict[str, Callable]:
    """
    Create effects adapter that matches MAExpert effect signatures.
    
    Returns dictionary of effect functions that can be used as drop-in
    replacements for MAExpert effects.
    
    Usage:
        effects = create_effects_adapter()
        embedding = effects['generate_embedding']('text to embed')
        llm_response = effects['call_llm']('prompt', temperature=0.7)
    """
    
    # Database effects (matching MAExpert database_client signatures)
    def insert_chunks(
        book_id: str,
        chunks: List[Dict[str, Any]],
        embeddings: List[List[float]]
    ) -> int:
        """
        Insert chunks with embeddings into database.
        Matches MAExpert signature: insert_chunks(book_id, chunks, embeddings)
        """
        try:
            chunk_ids = insert_chunks_batch(chunks, embeddings)
            return len(chunk_ids)
        except Exception as e:
            logger.error(f"Error inserting chunks: {e}", exc_info=True)
            raise
    
    def insert_book_record(
        title: str,
        author: Optional[str] = None,
        edition: Optional[str] = None,
        isbn: Optional[str] = None,
        total_pages: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Insert book record into database.
        Matches MAExpert signature: insert_book(metadata, pdf_data, total_pages)
        """
        try:
            book_id = insert_book(
                title=title,
                author=author,
                edition=edition,
                isbn=isbn,
                total_pages=total_pages,
                metadata=metadata
            )
            return book_id
        except Exception as e:
            logger.error(f"Error inserting book: {e}", exc_info=True)
            raise
    
    def search_chunks(
        query_embedding: List[float],
        chunk_types: Optional[List[str]] = None,
        book_id: Optional[str] = None,
        limit: int = 10,
        similarity_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Search chunks by vector similarity.
        Matches MAExpert signature: search_chunks(embedding, chunk_type, top_k, ...)
        """
        try:
            results = vector_similarity_search(
                query_embedding=query_embedding,
                chunk_types=chunk_types,
                book_id=book_id,
                limit=limit,
                similarity_threshold=similarity_threshold
            )
            return results
        except Exception as e:
            logger.error(f"Error searching chunks: {e}", exc_info=True)
            raise
    
    # LLM effects (matching MAExpert llm_client signatures)
    def call_llm(
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        system: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Call LLM (Claude via Bedrock).
        Matches MAExpert signature: call_llm(api_key, prompt, temperature)
        Note: api_key is handled via environment/IAM, not parameter
        """
        try:
            messages = [{"role": "user", "content": prompt}]
            response = invoke_claude(
                messages=messages,
                system=system,
                max_tokens=max_tokens,
                temperature=temperature
            )
            return {
                'text': response['content'],
                'usage': response.get('usage', {})
            }
        except Exception as e:
            logger.error(f"Error calling LLM: {e}", exc_info=True)
            raise
    
    # Embedding effects (matching MAExpert embedding_client signatures)
    def generate_embedding(text: str) -> List[float]:
        """
        Generate embedding for text.
        Matches MAExpert signature: generate_embedding(api_key, text)
        Note: api_key is handled via environment/IAM, not parameter
        """
        try:
            embeddings = generate_embeddings([text])
            return embeddings[0]
        except Exception as e:
            logger.error(f"Error generating embedding: {e}", exc_info=True)
            raise
    
    def generate_embeddings_batch(
        texts: List[str],
        batch_size: int = 100
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.
        Matches MAExpert signature: generate_embeddings_batch(texts, api_key, batch_size)
        """
        try:
            # Process in batches to avoid rate limits
            all_embeddings = []
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                batch_embeddings = generate_embeddings(batch)
                all_embeddings.extend(batch_embeddings)
            return all_embeddings
        except Exception as e:
            logger.error(f"Error generating embeddings batch: {e}", exc_info=True)
            raise
    
    # Figure description effects
    def describe_figure_with_context(
        image_bytes: bytes,
        context: Optional[str] = None
    ) -> str:
        """
        Describe a figure using Claude vision.
        Matches MAExpert signature: describe_figure(figure_info, context, api_key)
        """
        try:
            description = describe_figure(image_bytes, context)
            return description
        except Exception as e:
            logger.error(f"Error describing figure: {e}", exc_info=True)
            raise
    
    # Return adapter dictionary matching MAExpert effect interface
    return {
        # Database operations
        'insert_chunks': insert_chunks,
        'insert_book': insert_book_record,
        'search_chunks': search_chunks,
        
        # LLM operations
        'call_llm': call_llm,
        
        # Embedding operations
        'generate_embedding': generate_embedding,
        'generate_embeddings_batch': generate_embeddings_batch,
        
        # Figure operations
        'describe_figure': describe_figure_with_context,
        
        # Database connection (for direct access if needed)
        'get_db_connection': get_db_connection,
    }


def create_command_executor(effects: Optional[Dict[str, Callable]] = None):
    """
    Create command executor that dispatches commands to effects.
    Matches MAExpert command executor pattern.
    
    Args:
        effects: Optional effects dictionary. If None, creates default adapter.
    
    Returns:
        Command executor function
    """
    if effects is None:
        effects = create_effects_adapter()
    
    def execute_command(command: Any, context: Optional[Dict[str, Any]] = None) -> Any:
        """
        Execute a command by dispatching to appropriate effect.
        
        This matches MAExpert's command executor pattern, allowing
        direct reuse of command-based logic.
        """
        command_type = type(command).__name__
        
        # Map command types to effects
        if command_type == 'EmbedCommand':
            return effects['generate_embedding'](command.text)
        
        elif command_type == 'EmbedBatchCommand':
            return effects['generate_embeddings_batch'](command.texts, command.batch_size)
        
        elif command_type == 'LLMCommand':
            return effects['call_llm'](
                command.prompt,
                temperature=getattr(command, 'temperature', 0.7),
                max_tokens=getattr(command, 'max_tokens', 4096),
                system=getattr(command, 'system', None)
            )
        
        elif command_type == 'VectorSearchCommand':
            return effects['search_chunks'](
                query_embedding=command.query_embedding,
                chunk_types=getattr(command, 'chunk_types', None),
                book_id=getattr(command, 'book_id', None),
                limit=getattr(command, 'limit', 10),
                similarity_threshold=getattr(command, 'similarity_threshold', 0.7)
            )
        
        elif command_type == 'InsertChunksCommand':
            return effects['insert_chunks'](
                book_id=command.book_id,
                chunks=command.chunks,
                embeddings=command.embeddings
            )
        
        elif command_type == 'InsertBookCommand':
            return effects['insert_book'](
                title=command.title,
                author=getattr(command, 'author', None),
                edition=getattr(command, 'edition', None),
                isbn=getattr(command, 'isbn', None),
                total_pages=getattr(command, 'total_pages', None),
                metadata=getattr(command, 'metadata', None)
            )
        
        else:
            raise ValueError(f"Unknown command type: {command_type}")
    
    return execute_command

