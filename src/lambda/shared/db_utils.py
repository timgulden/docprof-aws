"""
Database utilities for Aurora PostgreSQL with pgvector
Handles connections via RDS Proxy with IAM authentication
"""

import os
import json
import boto3
import psycopg2
from psycopg2.extras import RealDictCursor, execute_values
from contextlib import contextmanager
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Cache for connection info
_connection_info_cache: Optional[Dict[str, Any]] = None


def get_db_connection_info() -> Dict[str, Any]:
    """
    Get database connection information from environment variables.
    For Lambda, these are set by Terraform.
    """
    global _connection_info_cache
    
    if _connection_info_cache:
        return _connection_info_cache
    
    # Get cluster endpoint from environment
    cluster_endpoint = os.getenv('DB_CLUSTER_ENDPOINT')
    if not cluster_endpoint:
        raise ValueError("DB_CLUSTER_ENDPOINT environment variable not set")
    
    # Get database name
    database = os.getenv('DB_NAME', 'docprof')
    
    # Get master username
    username = os.getenv('DB_MASTER_USERNAME', 'docprof_admin')
    
    # For IAM authentication, we'll use RDS Proxy or generate auth token
    # For now, using password from Secrets Manager (will switch to IAM later)
    password_secret_arn = os.getenv('DB_PASSWORD_SECRET_ARN')
    
    if password_secret_arn:
        # Get password from Secrets Manager
        secrets_client = boto3.client('secretsmanager')
        secret_response = secrets_client.get_secret_value(SecretId=password_secret_arn)
        password = secret_response['SecretString']
    else:
        # Fallback to direct password (not recommended for production)
        password = os.getenv('DB_PASSWORD', '')
    
    _connection_info_cache = {
        'host': cluster_endpoint,
        'port': 5432,
        'database': database,
        'user': username,
        'password': password
    }
    
    return _connection_info_cache


@contextmanager
def get_db_connection():
    """
    Context manager for database connections.
    Handles connection, commit, rollback, and cleanup.
    """
    conn_info = get_db_connection_info()
    
    conn = psycopg2.connect(
        host=conn_info['host'],
        port=conn_info['port'],
        database=conn_info['database'],
        user=conn_info['user'],
        password=conn_info['password'],
        connect_timeout=30
    )
    
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Database error: {e}", exc_info=True)
        raise
    finally:
        conn.close()


def vector_similarity_search(
    query_embedding: List[float],
    chunk_types: Optional[List[str]] = None,
    book_id: Optional[str] = None,
    limit: int = 10,
    similarity_threshold: float = 0.7
) -> List[Dict[str, Any]]:
    """
    Perform vector similarity search using pgvector.
    
    Args:
        query_embedding: Query vector (1536 dimensions)
        chunk_types: Filter by chunk types (None = all types)
        book_id: Filter by book_id (None = all books)
        limit: Maximum number of results
        similarity_threshold: Minimum similarity score (0-1)
    
    Returns:
        List of chunks with similarity scores
    """
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Build WHERE clause
            conditions = []
            params = [query_embedding]  # First param for similarity calculation
            
            if chunk_types:
                conditions.append("chunk_type = ANY(%s)")
                params.append(chunk_types)
            
            if book_id:
                conditions.append("book_id = %s")
                params.append(book_id)
            
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            
            # Add similarity threshold
            params.extend([query_embedding, similarity_threshold, query_embedding, limit])
            
            query = f"""
                SELECT 
                    chunk_id, book_id, chunk_type, content,
                    chapter_number, chapter_title,
                    page_start, page_end,
                    figure_id, figure_caption, figure_type, figure_context,
                    1 - (embedding <=> %s::vector) as similarity
                FROM chunks
                WHERE {where_clause}
                    AND embedding IS NOT NULL
                    AND 1 - (embedding <=> %s::vector) >= %s
                ORDER BY embedding <=> %s::vector
                LIMIT %s
            """
            
            cur.execute(query, params)
            return [dict(row) for row in cur.fetchall()]


def insert_chunks_batch(
    chunks: List[Dict[str, Any]],
    embeddings: List[List[float]]
) -> List[str]:
    """
    Batch insert chunks with embeddings.
    
    Args:
        chunks: List of chunk dictionaries
        embeddings: List of embedding vectors (1536 dimensions each)
    
    Returns:
        List of inserted chunk_ids
    """
    if len(chunks) != len(embeddings):
        raise ValueError("chunks and embeddings must have same length")
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Prepare data for batch insert
            values = [
                (
                    chunk['book_id'],
                    chunk['chunk_type'],
                    chunk['content'],
                    embedding,
                    chunk.get('chapter_number'),
                    chunk.get('chapter_title'),
                    chunk.get('section_title'),
                    chunk.get('page_start'),
                    chunk.get('page_end'),
                    chunk.get('keywords', []),
                    chunk.get('figure_id'),
                    chunk.get('figure_caption'),
                    chunk.get('figure_type'),
                    chunk.get('figure_context') or chunk.get('context_text'),  # MAExpert uses 'context_text', map to 'figure_context'
                    json.dumps(chunk.get('metadata')) if chunk.get('metadata') else None  # Convert dict to JSON string for JSONB
                )
                for chunk, embedding in zip(chunks, embeddings)
            ]
            
            # Batch insert
            chunk_ids = execute_values(
                cur,
                """
                INSERT INTO chunks (
                    book_id, chunk_type, content, embedding,
                    chapter_number, chapter_title, section_title,
                    page_start, page_end, keywords,
                    figure_id, figure_caption, figure_type, figure_context,
                    metadata
                )
                VALUES %s
                RETURNING chunk_id
                """,
                values,
                template="""(
                    %s, %s, %s, %s::vector,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s
                )""",
                fetch=True
            )
            
            return [str(row[0]) for row in chunk_ids]


def insert_book(
    title: str,
    author: Optional[str] = None,
    edition: Optional[str] = None,
    isbn: Optional[str] = None,
    total_pages: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> str:
    """
    Insert a book and return book_id.
    
    Args:
        title: Book title
        author: Author name
        edition: Edition information
        isbn: ISBN
        total_pages: Total number of pages
        metadata: Additional metadata as dict
    
    Returns:
        book_id (UUID string)
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO books (title, author, edition, isbn, total_pages, metadata)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                RETURNING book_id
                """,
                (title, author, edition, isbn, total_pages, json.dumps(metadata) if metadata else None)
            )
            return str(cur.fetchone()[0])


def insert_figures_batch(
    book_id: str,
    figures: List[Dict[str, Any]]
) -> List[str]:
    """
    Batch insert figures.
    
    Args:
        book_id: Book UUID
        figures: List of figure dictionaries with:
            - page_number: int
            - image_data: bytes
            - image_format: str (e.g., 'png', 'jpeg')
            - width: int
            - height: int
            - caption: str (optional)
            - metadata: dict (optional)
    
    Returns:
        List of inserted figure_ids
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            values = [
                (
                    book_id,
                    fig['page_number'],
                    fig['image_data'],
                    fig['image_format'],
                    fig.get('width'),
                    fig.get('height'),
                    fig.get('caption'),
                    json.dumps(fig.get('metadata')) if fig.get('metadata') else None
                )
                for fig in figures
            ]
            
            figure_ids = execute_values(
                cur,
                """
                INSERT INTO figures (
                    book_id, page_number, image_data, image_format,
                    width, height, caption, metadata
                )
                VALUES %s
                RETURNING figure_id
                """,
                values,
                template="""(%s, %s, %s, %s, %s, %s, %s, %s::jsonb)""",
                fetch=True
            )
            
            return [str(row[0]) for row in figure_ids]

