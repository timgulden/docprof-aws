"""
Helper functions for managing selected book filters across features.

This provides a reusable way to:
- Get selected book_ids from session or request
- Update selected book_ids in session
- Apply book filter to vector searches

Used by:
- Chat handler
- Lecture handler
- Course generator
- Any other feature that needs book filtering
"""

from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)


def get_selected_book_ids(
    session: Dict[str, Any],
    request_book_ids: Optional[List[str]] = None
) -> Optional[List[str]]:
    """
    Get selected book_ids, preferring request over session.
    
    This allows:
    - Request to override session selection (temporary filter)
    - Session to persist selection across requests (default behavior)
    - None if neither is set (search all books)
    
    Args:
        session: Session dictionary from session_manager
        request_book_ids: Optional book_ids from request body
    
    Returns:
        List of book_ids to filter by, or None to search all books
    """
    # Prefer request book_ids if provided (allows temporary override)
    if request_book_ids and len(request_book_ids) > 0:
        logger.debug(f"Using book_ids from request: {len(request_book_ids)} books")
        return request_book_ids
    
    # Fall back to session book_ids
    session_book_ids = session.get('selected_book_ids')
    if session_book_ids and len(session_book_ids) > 0:
        logger.debug(f"Using book_ids from session: {len(session_book_ids)} books")
        return session_book_ids
    
    # No filter - search all books
    logger.debug("No book_ids in request or session - searching all books")
    return None


def update_selected_book_ids(
    session: Dict[str, Any],
    book_ids: Optional[List[str]]
) -> Dict[str, Any]:
    """
    Update selected_book_ids in session and return updated session.
    
    Args:
        session: Session dictionary
        book_ids: New list of selected book_ids (None or [] to clear)
    
    Returns:
        Updated session dictionary
    """
    if book_ids is None:
        book_ids = []
    
    session['selected_book_ids'] = book_ids
    logger.info(f"Updated session {session.get('session_id')} with {len(book_ids)} selected book(s)")
    
    return session
