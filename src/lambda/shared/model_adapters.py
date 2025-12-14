"""
Adapters for converting between core Pydantic models and AWS data structures.
Allows us to use pure logic functions directly while working with DynamoDB dicts.

Logic is part of this codebase in shared/logic/ and shared/core/.
Gets packaged with Lambda functions via shared/ directory.
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Logic is in shared/ directory, packaged with Lambda functions
# Import directly: from shared.logic.chat import ...
from shared.core.chat_models import ChatMessage, ChatState, SourceCitation
from shared.logic.chat import expand_query_for_retrieval, build_synthesis_prompt
from shared.core.prompts import get_prompt


def dict_to_chat_message(msg_dict: Dict[str, Any]) -> ChatMessage:
    """Convert DynamoDB message dict to MAExpert ChatMessage."""
    
    # Parse timestamp
    timestamp = msg_dict.get('timestamp')
    if isinstance(timestamp, str):
        timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    elif timestamp is None:
        timestamp = datetime.utcnow()
    
    # Convert sources if present
    sources = []
    if msg_dict.get('sources'):
        for src_dict in msg_dict['sources']:
            sources.append(SourceCitation(**src_dict))
    
    return ChatMessage(
        id=msg_dict.get('id', ''),
        role=msg_dict.get('role', 'user'),
        content=msg_dict.get('content', ''),
        timestamp=timestamp,
        sources=sources,
        figures=msg_dict.get('figures', []),
        audio_url=msg_dict.get('audio_url'),
        citation_spans=msg_dict.get('citation_spans', []),
        general_spans=msg_dict.get('general_spans', [])
    )


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


def chat_message_to_dict(msg: ChatMessage) -> Dict[str, Any]:
    """Convert MAExpert ChatMessage to DynamoDB-compatible dict."""
    result = {
        'id': msg.id,
        'role': msg.role,
        'content': msg.content,
        'timestamp': msg.timestamp.isoformat() if isinstance(msg.timestamp, datetime) else str(msg.timestamp),
        'sources': [src.model_dump(mode='json') for src in msg.sources] if msg.sources else [],
        'figures': [fig.model_dump(mode='json') for fig in msg.figures] if msg.figures else [],
    }
    
    if msg.audio_url:
        result['audio_url'] = msg.audio_url
    if msg.citation_spans:
        result['citation_spans'] = [span.model_dump(mode='json') for span in msg.citation_spans]
    if msg.general_spans:
        result['general_spans'] = [span.model_dump(mode='json') for span in msg.general_spans]
    
    # Clean for DynamoDB (convert floats to strings)
    return _clean_for_dynamodb(result)


def dict_to_chat_state(session_dict: Dict[str, Any]) -> ChatState:
    """Convert DynamoDB session dict to MAExpert ChatState."""
    
    # Parse timestamps
    created_at = session_dict.get('created_at')
    if isinstance(created_at, str):
        created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
    elif created_at is None:
        created_at = datetime.utcnow()
    
    updated_at = session_dict.get('updated_at')
    if isinstance(updated_at, str):
        updated_at = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
    elif updated_at is None:
        updated_at = datetime.utcnow()
    
    # Convert messages
    messages = []
    for msg_dict in session_dict.get('messages', []):
        messages.append(dict_to_chat_message(msg_dict))
    
    return ChatState(
        session_id=session_dict.get('session_id'),
        session_name=session_dict.get('session_name'),
        session_type=session_dict.get('session_type', 'chat'),
        session_context=session_dict.get('session_context'),
        created_at=created_at,
        updated_at=updated_at,
        messages=messages,
        status=session_dict.get('status', 'idle'),
        error=session_dict.get('error'),
        ui_message=session_dict.get('ui_message')
    )


def chat_state_to_dict(state: ChatState) -> Dict[str, Any]:
    """Convert MAExpert ChatState to DynamoDB-compatible dict."""
    result = {
        'session_id': state.session_id,
        'session_name': state.session_name,
        'session_type': state.session_type,
        'session_context': state.session_context,
        'created_at': state.created_at.isoformat() if isinstance(state.created_at, datetime) else str(state.created_at),
        'updated_at': state.updated_at.isoformat() if isinstance(state.updated_at, datetime) else str(state.updated_at),
        'messages': [chat_message_to_dict(msg) for msg in state.messages],
        'status': state.status,
    }
    
    if state.error:
        result['error'] = state.error.model_dump(mode='json') if hasattr(state.error, 'model_dump') else state.error
    if state.ui_message:
        result['ui_message'] = state.ui_message
    
    return result


def get_expand_query():
    """Get expand_query_for_retrieval function."""
    return expand_query_for_retrieval


def get_build_prompt():
    """Get build_synthesis_prompt function."""
    return build_synthesis_prompt


def get_system_prompt() -> str:
    """Get system prompt for chat."""
    return get_prompt("chat.system")
