"""
Lambda function to update book metadata.
"""

import json
import logging
from typing import Dict, Any

from shared.db_utils import get_db_connection

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Update book metadata."""
    
    book_id = event.get('book_id')
    title = event.get('title')
    author = event.get('author')
    edition = event.get('edition')
    isbn = event.get('isbn')
    
    if not book_id:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'book_id is required'})
        }
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Build UPDATE query dynamically based on provided fields
                updates = []
                params = []
                
                if title:
                    updates.append("title = %s")
                    params.append(title)
                
                if author:
                    updates.append("author = %s")
                    params.append(author)
                
                if edition:
                    updates.append("edition = %s")
                    params.append(edition)
                
                if isbn:
                    updates.append("isbn = %s")
                    params.append(isbn)
                
                if not updates:
                    return {
                        'statusCode': 400,
                        'body': json.dumps({'error': 'No fields to update'})
                    }
                
                # Add book_id to params
                params.append(book_id)
                
                query = f"""
                    UPDATE books
                    SET {', '.join(updates)}
                    WHERE book_id = %s
                    RETURNING book_id, title, author, edition, isbn
                """
                
                cur.execute(query, params)
                result = cur.fetchone()
                
                if not result:
                    return {
                        'statusCode': 404,
                        'body': json.dumps({'error': f'Book {book_id} not found'})
                    }
                
                conn.commit()
                
                updated_book = {
                    'book_id': str(result[0]),
                    'title': result[1],
                    'author': result[2],
                    'edition': result[3],
                    'isbn': result[4]
                }
                
                logger.info(f"Updated book {book_id}: {updated_book}")
                
                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'message': 'Book updated successfully',
                        'book': updated_book
                    }, indent=2, default=str)
                }
                
    except Exception as e:
        logger.error(f"Error updating book: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'message': 'Failed to update book'
            })
        }

