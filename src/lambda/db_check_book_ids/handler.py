"""
Lambda function to check book_id consistency between books and chunks.
"""

import json
import logging
from typing import Dict, Any

from shared.db_utils import get_db_connection
from psycopg2.extras import RealDictCursor

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Check book_id consistency."""
    
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get all books
                cur.execute("SELECT book_id, title FROM books")
                books = cur.fetchall()
                
                # Get book_ids from chunks
                cur.execute("SELECT DISTINCT book_id, COUNT(*) as chunk_count FROM chunks GROUP BY book_id")
                chunk_book_ids = cur.fetchall()
                
                # Get book_ids from figures
                cur.execute("SELECT DISTINCT book_id, COUNT(*) as figure_count FROM figures GROUP BY book_id")
                figure_book_ids = cur.fetchall()
                
                # Get book_ids from chapter_documents
                cur.execute("SELECT DISTINCT book_id, COUNT(*) as chapter_count FROM chapter_documents GROUP BY book_id")
                chapter_book_ids = cur.fetchall()
                
                # Build result
                result = {
                    'books': [dict(b) for b in books],
                    'chunk_book_ids': [dict(c) for c in chunk_book_ids],
                    'figure_book_ids': [dict(f) for f in figure_book_ids],
                    'chapter_book_ids': [dict(ch) for ch in chapter_book_ids],
                    'consistency_check': {}
                }
                
                # Check consistency
                book_ids_in_books = {str(b['book_id']) for b in books}
                book_ids_in_chunks = {str(c['book_id']) for c in chunk_book_ids}
                book_ids_in_figures = {str(f['book_id']) for f in figure_book_ids}
                book_ids_in_chapters = {str(ch['book_id']) for ch in chapter_book_ids}
                
                # Find orphaned chunks (chunks with book_id not in books table)
                orphaned_chunks = book_ids_in_chunks - book_ids_in_books
                orphaned_figures = book_ids_in_figures - book_ids_in_books
                orphaned_chapters = book_ids_in_chapters - book_ids_in_books
                
                # Find books with no chunks
                books_without_chunks = book_ids_in_books - book_ids_in_chunks
                
                result['consistency_check'] = {
                    'all_book_ids_match': len(orphaned_chunks) == 0 and len(orphaned_figures) == 0 and len(orphaned_chapters) == 0,
                    'orphaned_chunks': list(orphaned_chunks),
                    'orphaned_figures': list(orphaned_figures),
                    'orphaned_chapters': list(orphaned_chapters),
                    'books_without_chunks': list(books_without_chunks),
                    'book_ids_in_books': list(book_ids_in_books),
                    'book_ids_in_chunks': list(book_ids_in_chunks),
                    'book_ids_in_figures': list(book_ids_in_figures),
                    'book_ids_in_chapters': list(book_ids_in_chapters)
                }
                
                return {
                    'statusCode': 200,
                    'body': json.dumps(result, indent=2, default=str)
                }
                
    except Exception as e:
        logger.error(f"Error checking book_ids: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'message': 'Failed to check book_ids'
            })
        }

