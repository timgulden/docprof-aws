"""
Session manager for DynamoDB-backed chat sessions.
Adapts MAExpert's file-based session manager to use DynamoDB.

Matches MAExpert patterns:
- ChatState model structure
- Session CRUD operations
- TTL-based expiration
"""

import os
import json
import boto3
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from uuid import uuid4
import logging

logger = logging.getLogger(__name__)

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb')

# Get table name from environment (set by Terraform)
TABLE_NAME = os.getenv('DYNAMODB_SESSIONS_TABLE_NAME', 'docprof-dev-sessions')

# Session TTL: 7 days (in seconds)
SESSION_TTL_SECONDS = 7 * 24 * 60 * 60


def get_table():
    """Get DynamoDB table instance."""
    return dynamodb.Table(TABLE_NAME)


def create_session(
    session_id: Optional[str] = None,
    session_name: Optional[str] = None,
    session_type: str = "chat",
    session_context: Optional[str] = None,
    selected_book_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Create a new chat session.
    
    Matches MAExpert SessionManager.create_session signature.
    
    Args:
        session_id: Optional session ID (generated if not provided)
        session_name: Optional user-friendly session name
        session_type: Session type (chat, lecture, quiz, case_study)
        session_context: Optional context for guiding conversation
        selected_book_ids: Optional list of selected book IDs for filtering search
    
    Returns:
        Session dictionary matching ChatState structure
    """
    if not session_id:
        session_id = str(uuid4())
    
    now = datetime.now(timezone.utc)
    expires_at = int((now + timedelta(seconds=SESSION_TTL_SECONDS)).timestamp())
    
    session_data = {
        'session_id': session_id,
        'session_name': session_name,
        'session_type': session_type,
        'session_context': session_context,
        'selected_book_ids': selected_book_ids or [],  # Store selected books for filtering
        'created_at': now.isoformat(),
        'updated_at': now.isoformat(),
        'messages': [],
        'status': 'idle',
        'error': None,
        'ui_message': None,
        'expires_at': expires_at,  # TTL attribute
    }
    
    try:
        table = get_table()
        table.put_item(Item=session_data)
        logger.info(f"Created session {session_id}")
        return session_data
    except Exception as e:
        logger.error(f"Failed to create session: {e}", exc_info=True)
        raise


def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    """
    Load a chat session by session_id.
    
    Matches MAExpert SessionManager.get_session signature.
    
    Args:
        session_id: Session ID to retrieve
    
    Returns:
        Session dictionary or None if not found
    """
    try:
        table = get_table()
        response = table.get_item(Key={'session_id': session_id})
        
        if 'Item' not in response:
            logger.debug(f"Session {session_id} not found")
            return None
        
        item = response['Item']
        
        # Convert DynamoDB types to Python types
        # Messages are stored as list of dicts (DynamoDB list type)
        # Timestamps are ISO format strings
        return item
        
    except Exception as e:
        logger.error(f"Failed to get session {session_id}: {e}", exc_info=True)
        return None


def _clean_for_dynamodb(value: Any) -> Any:
    """Recursively clean data structure for DynamoDB compatibility.
    
    DynamoDB doesn't support float types - convert to string.
    Also handles nested dicts and lists.
    """
    if isinstance(value, float):
        return str(value)  # Convert float to string
    elif isinstance(value, dict):
        return {k: _clean_for_dynamodb(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_clean_for_dynamodb(item) for item in value]
    else:
        return value


def update_session(session_data: Dict[str, Any]) -> None:
    """
    Save updated chat session state.
    
    Matches MAExpert SessionManager.update_session signature.
    Expects session_data dict matching ChatState structure.
    
    Args:
        session_data: Session dictionary with updated state
    """
    session_id = session_data.get('session_id')
    if not session_id:
        raise ValueError("Cannot update session without session_id")
    
    # Update timestamp
    now = datetime.now(timezone.utc)
    session_data['updated_at'] = now.isoformat()
    
    # Ensure selected_book_ids exists (for backward compatibility)
    if 'selected_book_ids' not in session_data:
        session_data['selected_book_ids'] = []
    
    # Update TTL (extend expiration)
    expires_at = int((now + timedelta(seconds=SESSION_TTL_SECONDS)).timestamp())
    session_data['expires_at'] = expires_at
    
    # Clean data for DynamoDB compatibility (convert floats to strings)
    cleaned_data = _clean_for_dynamodb(session_data)
    
    try:
        table = get_table()
        table.put_item(Item=cleaned_data)
        logger.debug(f"Updated session {session_id}")
    except Exception as e:
        logger.error(f"Failed to update session {session_id}: {e}", exc_info=True)
        raise


def delete_session(session_id: str) -> None:
    """
    Delete a chat session.
    
    Matches MAExpert SessionManager.delete_session signature.
    
    Args:
        session_id: Session ID to delete
    """
    try:
        table = get_table()
        table.delete_item(Key={'session_id': session_id})
        logger.info(f"Deleted session {session_id}")
    except Exception as e:
        logger.error(f"Failed to delete session {session_id}: {e}", exc_info=True)
        raise


def list_sessions(user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    List all sessions (optionally filtered by user_id).
    
    Matches MAExpert SessionManager.list_sessions signature.
    Note: user_id filtering not yet implemented (will need GSI).
    
    Returns:
        List of session metadata dictionaries with:
        - session_id
        - session_name
        - session_type
        - created_at
        - updated_at
        - message_count
        - last_message_preview (first 100 chars of last message)
    """
    try:
        table = get_table()
        
        # Scan table (will be slow for large datasets, but fine for dev)
        # TODO: Add GSI for user_id if needed for production
        response = table.scan()
        items = response.get('Items', [])
        
        sessions = []
        for item in items:
            try:
                session_id = item.get('session_id')
                if not session_id:
                    continue
                
                messages = item.get('messages', [])
                
                # Auto-generate session name if missing
                session_name = item.get('session_name')
                if not session_name and messages:
                    # Try to get first user message as name
                    for msg in messages:
                        if isinstance(msg, dict) and msg.get('role') == 'user':
                            content = msg.get('content', '')
                            session_name = content[:50] + ('...' if len(content) > 50 else '')
                            break
                
                if not session_name:
                    # Use creation time or default
                    created = item.get('created_at')
                    if created:
                        try:
                            if isinstance(created, str):
                                dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                            else:
                                dt = created
                            if dt.tzinfo is None:
                                dt = dt.replace(tzinfo=timezone.utc)
                            session_name = f"Chat {dt.strftime('%Y-%m-%d %H:%M')}"
                        except Exception:
                            session_name = "Untitled Chat"
                    else:
                        session_name = "Untitled Chat"
                
                # Parse timestamps
                updated_at = item.get('updated_at') or item.get('created_at')
                created_at = item.get('created_at')
                
                if updated_at and isinstance(updated_at, str):
                    updated_at = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                elif updated_at is None:
                    updated_at = datetime.now(timezone.utc)
                
                if created_at and isinstance(created_at, str):
                    created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                elif created_at is None:
                    created_at = datetime.now(timezone.utc)
                
                # Ensure timezone-aware
                if updated_at.tzinfo is None:
                    updated_at = updated_at.replace(tzinfo=timezone.utc)
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                
                session_meta = {
                    'session_id': session_id,
                    'session_name': session_name,
                    'session_type': item.get('session_type', 'chat'),
                    'created_at': created_at,
                    'updated_at': updated_at,
                    'message_count': len(messages),
                }
                
                # Get last message preview
                if messages:
                    last_msg = messages[-1]
                    if isinstance(last_msg, dict):
                        preview = last_msg.get('content', '')[:100]
                        session_meta['last_message_preview'] = preview
                    else:
                        session_meta['last_message_preview'] = None
                else:
                    session_meta['last_message_preview'] = None
                
                sessions.append(session_meta)
            except Exception as e:
                logger.warning(f"Error processing session item: {e}", exc_info=True)
                continue
        
        # Sort by updated_at descending (most recent first)
        sessions.sort(key=lambda x: x.get('updated_at') or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        
        return sessions
        
    except Exception as e:
        logger.error(f"Failed to list sessions: {e}", exc_info=True)
        return []
