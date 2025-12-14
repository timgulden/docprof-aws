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
    """
    try:
        books = fetch_all_books()
        return success_response(books)
    except Exception as e:
        logger.error(f"Error fetching books: {e}", exc_info=True)
        return error_response(f"Failed to fetch books: {str(e)}", 500)


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

