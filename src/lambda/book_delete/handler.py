"""
Book Delete Lambda Handler
Handles DELETE requests to remove books from the database
"""

import logging
from typing import Dict, Any

from shared.response import success_response, error_response
from shared.protocol_implementations import AWSDatabaseClient

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle DELETE /books/{bookId} request.
    
    Deletes the book and all associated data (chunks, figures, chapter documents).
    """
    try:
        # Extract book_id from path parameters
        path_params = event.get('pathParameters') or {}
        book_id = path_params.get('bookId')
        
        if not book_id:
            return error_response("Book ID is required", 400)
        
        logger.info(f"Deleting book: {book_id}")
        
        # Delete book and all associated data
        database = AWSDatabaseClient()
        database.delete_book_contents(book_id, delete_book=True)
        
        logger.info(f"Successfully deleted book: {book_id}")
        
        return success_response({
            'book_id': book_id,
            'status': 'deleted',
            'message': 'Book and all associated data deleted successfully'
        })
        
    except Exception as e:
        logger.error(f"Error deleting book: {e}", exc_info=True)
        return error_response(f"Failed to delete book: {str(e)}", 500)

