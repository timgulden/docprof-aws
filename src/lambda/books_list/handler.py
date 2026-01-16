"""
Books List Lambda Handler
Fetches all books from the database for the frontend
"""

import json
import logging
from typing import Dict, Any, List
from datetime import datetime

from shared.db_utils import get_db_connection
from shared.response import success_response, error_response

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle GET /books request to fetch all books.
    Also supports PATCH operations for updating book metadata.
    
    For GET:
    Returns list of books with:
    - book_id (UUID as string)
    - title
    - author
    - edition
    - isbn
    - total_pages
    - ingestion_date
    - created_at
    - metadata
    
    For PATCH (update_metadata action):
    Body: {
        "action": "update_metadata",
        "book_id": "uuid",
        "title": "...",
        "author": "...",
        "edition": "..."
    }
    """
    try:
        # Check if this is an update request
        if event.get('action') == 'update_metadata':
            return update_book_metadata(event)
        
        # Otherwise, fetch all books
        books = fetch_all_books()
        return success_response(books)
    except Exception as e:
        logger.error(f"Error handling request: {e}", exc_info=True)
        return error_response(f"Failed to process request: {str(e)}", 500)


def update_book_metadata(event: Dict[str, Any]) -> Dict[str, Any]:
    """Update metadata for a specific book."""
    book_id = event.get('book_id')
    title = event.get('title')
    author = event.get('author')
    edition = event.get('edition')
    
    if not book_id:
        return error_response("book_id is required", 400)
    
    logger.info(f"Updating metadata for book {book_id}")
    logger.info(f"  Title: {title}")
    logger.info(f"  Author: {author}")
    logger.info(f"  Edition: {edition}")
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Build UPDATE query dynamically based on provided fields
                update_fields = []
                params = []
                
                if title is not None:
                    update_fields.append("title = %s")
                    params.append(title)
                
                if author is not None:
                    update_fields.append("author = %s")
                    params.append(author)
                
                if edition is not None:
                    update_fields.append("edition = %s")
                    params.append(edition)
                
                if not update_fields:
                    return error_response("No fields to update", 400)
                
                # Add book_id to params
                params.append(book_id)
                
                query = f"""
                    UPDATE books
                    SET {', '.join(update_fields)}
                    WHERE book_id = %s
                    RETURNING book_id, title, author, edition, total_pages
                """
                
                cur.execute(query, params)
                result = cur.fetchone()
                
                if not result:
                    return error_response(f"Book {book_id} not found", 404)
                
                updated_book = {
                    'book_id': str(result[0]),
                    'title': result[1],
                    'author': result[2],
                    'edition': result[3],
                    'total_pages': result[4]
                }
                
                logger.info(f"Successfully updated book {book_id}")
                return success_response({
                    'message': 'Book metadata updated successfully',
                    'book': updated_book
                })
                
    except Exception as e:
        logger.error(f"Error updating book metadata: {e}", exc_info=True)
        return error_response(f"Failed to update book metadata: {str(e)}", 500)


def fetch_all_books() -> List[Dict[str, Any]]:
    """Fetch all books from the database"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Try to select with ingestion_status columns, fall back if they don't exist
            use_ingestion_columns = False
            try:
                cur.execute("""
                    SELECT 
                        book_id,
                        title,
                        author,
                        edition,
                        isbn,
                        total_pages,
                        ingestion_date,
                        ingestion_status,
                        ingestion_started_at,
                        ingestion_completed_at,
                        created_at,
                        metadata
                    FROM books
                    ORDER BY created_at DESC
                """)
                rows = cur.fetchall()
                # Columns exist - use all fields
                use_ingestion_columns = True
            except Exception as e:
                if 'ingestion_status' in str(e) or 'does not exist' in str(e):
                    # Columns don't exist - rollback and use basic query
                    conn.rollback()
                    logger.info("ingestion_status columns not found, using basic query")
                    cur.execute("""
                        SELECT 
                            book_id,
                            title,
                            author,
                            edition,
                            isbn,
                            total_pages,
                            ingestion_date,
                            created_at,
                            metadata
                        FROM books
                        ORDER BY created_at DESC
                    """)
                    rows = cur.fetchall()
                    use_ingestion_columns = False
                else:
                    raise
            
            books = []
            for row in rows:
                if use_ingestion_columns:
                    book = {
                        'book_id': str(row[0]),
                        'title': row[1] or 'Untitled',
                        'author': row[2] or '',
                        'edition': row[3] or '',
                        'isbn': row[4] or '',
                        'total_pages': row[5] or 0,
                        'ingestion_date': row[6].isoformat() if row[6] else None,
                        'ingestion_status': row[7] or None,
                        'ingestion_started_at': row[8].isoformat() if row[8] else None,
                        'ingestion_completed_at': row[9].isoformat() if row[9] else None,
                        'created_at': row[10].isoformat() if row[10] else None,
                        'metadata': row[11] if row[11] else {}
                    }
                else:
                    book = {
                        'book_id': str(row[0]),
                        'title': row[1] or 'Untitled',
                        'author': row[2] or '',
                        'edition': row[3] or '',
                        'isbn': row[4] or '',
                        'total_pages': row[5] or 0,
                        'ingestion_date': row[6].isoformat() if row[6] else None,
                        'ingestion_status': None,
                        'ingestion_started_at': None,
                        'ingestion_completed_at': None,
                        'created_at': row[7].isoformat() if row[7] else None,
                        'metadata': row[8] if row[8] else {}
                    }
                books.append(book)
            
            logger.info(f"Fetched {len(books)} books from database")
            return books

