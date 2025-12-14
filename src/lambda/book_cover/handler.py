"""
Book Cover Lambda Handler
Returns book cover images from database metadata (consistent with figures storage).
"""

import logging
import base64
from typing import Dict, Any

from shared.response import error_response
from shared.db_utils import get_db_connection

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle GET /books/{bookId}/cover request.
    
    Retrieves cover image from database metadata (same pattern as figures).
    """
    # Extract book_id from path parameters
    path_params = event.get('pathParameters') or {}
    book_id = path_params.get('bookId')
    
    if not book_id:
        return error_response("Book ID is required", 400)
    
    logger.info(f"Cover requested for book_id: {book_id}")
    
    # Retrieve from database metadata (consistent with figures)
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # First check if book exists - also check all books to debug
                cur.execute("SELECT book_id FROM books WHERE book_id = %s", (book_id,))
                book_exists = cur.fetchone()
                
                # Debug: Check how many books exist
                cur.execute("SELECT COUNT(*) FROM books")
                total_books = cur.fetchone()[0]
                logger.info(f"Total books in database: {total_books}")
                
                if not book_exists:
                    logger.warning(f"Book not found in database: {book_id}")
                    # Debug: List all book IDs
                    cur.execute("SELECT book_id FROM books LIMIT 10")
                    all_book_ids = [row[0] for row in cur.fetchall()]
                    logger.info(f"Sample book IDs in database: {all_book_ids}")
                    return error_response("Book not found", 404)
                
                # Now check for cover - get full metadata to debug
                cur.execute(
                    """
                    SELECT metadata->'cover'->>'format', metadata->'cover'->>'data', metadata, metadata->'cover'
                    FROM books
                    WHERE book_id = %s
                    """,
                    (book_id,)
                )
                row = cur.fetchone()
                
                # Log what we found for debugging
                if row:
                    metadata = row[2] if len(row) > 2 else None
                    cover_obj = row[3] if len(row) > 3 else None
                    logger.info(f"Book found. Cover format: {row[0]}, Cover data present: {bool(row[1])}, Metadata keys: {list(metadata.keys()) if metadata else 'null'}, Cover object: {cover_obj}")
                else:
                    logger.warning(f"Book found but no row returned for cover query: {book_id}")
                
                if row and row[0] and row[1]:
                    cover_format = row[0]
                    cover_data_hex = row[1]
                    
                    # Decode hex to bytes
                    cover_bytes = bytes.fromhex(cover_data_hex)
                    content_type = f'image/{cover_format}'
                    
                    logger.info(f"Retrieved cover from database for book_id: {book_id}, format: {cover_format}")
                    
                    # Return as binary image - API Gateway will handle base64 encoding automatically
                    # Set isBase64Encoded to true so API Gateway knows to decode it
                    base64_data = base64.b64encode(cover_bytes).decode('utf-8')
                    
                    return {
                        'statusCode': 200,
                        'headers': {
                            'Content-Type': content_type,
                            'Access-Control-Allow-Origin': '*',
                        },
                        'body': base64_data,
                        'isBase64Encoded': True
                    }
                else:
                    logger.warning(f"Cover not found in database for book_id: {book_id}")
                    return error_response("Cover image not found", 404)
                    
    except Exception as e:
        logger.error(f"Error retrieving cover from database: {e}", exc_info=True)
        return error_response("Failed to retrieve cover image", 500)

