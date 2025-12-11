"""
Unit tests for chat logic functions.

These tests run locally, require no AWS infrastructure, and are fast.
They test pure logic functions in isolation.
"""

import pytest
import sys
import os
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

# Add Lambda source to path - this allows "from shared.core" imports to work
lambda_path = Path(__file__).parent.parent.parent / "src" / "lambda"
sys.path.insert(0, str(lambda_path))

# Mock all AWS/database dependencies before any imports
# Create proper mock modules with submodules
class MockModule:
    def __getattr__(self, name):
        return MagicMock()

# Mock boto3 and botocore
sys.modules['boto3'] = MockModule()
botocore_mock = MockModule()
botocore_mock.exceptions = MockModule()
botocore_mock.exceptions.ClientError = Exception
sys.modules['botocore'] = botocore_mock
sys.modules['botocore.exceptions'] = botocore_mock.exceptions

# Mock psycopg2 with submodules
psycopg2_mock = MockModule()
psycopg2_mock.extras = MockModule()
psycopg2_mock.extras.RealDictCursor = MagicMock
psycopg2_mock.extras.execute_values = MagicMock
psycopg2_mock.pool = MockModule()
sys.modules['psycopg2'] = psycopg2_mock
sys.modules['psycopg2.extras'] = psycopg2_mock.extras
sys.modules['psycopg2.pool'] = psycopg2_mock.pool

# Now we can import normally - the shared/__init__.py will import mocked dependencies
from shared.logic.chat import expand_query_for_retrieval, build_synthesis_prompt
from shared.core.chat_models import ChatMessage, ChatState, SourceCitation
from shared.core.prompts import get_prompt


class TestExpandQueryForRetrieval:
    """Test expand_query_for_retrieval function."""
    
    def test_simple_query(self):
        """Test basic query expansion."""
        result = expand_query_for_retrieval("test query")
        assert isinstance(result, str)
        assert len(result) > 0
        assert "test query" in result.lower()
    
    def test_query_with_variations(self):
        """Test that common variations are normalized."""
        # Test goodwill normalization
        result = expand_query_for_retrieval("good will accounting")
        assert "goodwill" in result.lower()
    
    def test_query_with_conversation_history(self):
        """Test query expansion with conversation history."""
        history = [
            ChatMessage(role="user", content="What is DCF?"),
            ChatMessage(role="assistant", content="DCF stands for Discounted Cash Flow...")
        ]
        result = expand_query_for_retrieval(
            "tell me more",
            conversation_history=history
        )
        assert isinstance(result, str)
        assert len(result) > len("tell me more")  # Should be expanded
    
    def test_query_with_session_context(self):
        """Test query expansion with figure context."""
        session_context = """
=== FIGURES SHOWN IN LECTURE ===
Figure 1: DCF Valuation Model
  - Description: Shows how to calculate present value
  - Explanation: Discounts future cash flows
"""
        result = expand_query_for_retrieval(
            "explain this figure",
            session_context=session_context
        )
        assert isinstance(result, str)
        # Should include figure keywords
        assert "dcf" in result.lower() or "valuation" in result.lower()
    
    def test_empty_query(self):
        """Test handling of empty query."""
        result = expand_query_for_retrieval("")
        assert isinstance(result, str)
        # Should handle gracefully, not crash


class TestBuildSynthesisPrompt:
    """Test build_synthesis_prompt function."""
    
    def test_basic_prompt_building(self):
        """Test basic prompt construction."""
        chunks = [
            {
                'content': 'Test chunk content',
                'chapter_title': 'Test Chapter',
                'page_start': 1,
                'page_end': 1,
                'chunk_type': 'chapter'
            }
        ]
        messages = [
            ChatMessage(role="user", content="Test question")
        ]
        
        prompt = build_synthesis_prompt(
            user_message="Test question",
            conversation_history=messages,
            chunks=chunks
        )
        
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "Test question" in prompt
        assert "Test chunk content" in prompt
    
    def test_prompt_with_multiple_chunks(self):
        """Test prompt with multiple chunks."""
        chunks = [
            {
                'content': 'First chunk',
                'chapter_title': 'Chapter 1',
                'page_start': 1,
                'page_end': 1,
                'chunk_type': 'chapter'
            },
            {
                'content': 'Second chunk',
                'chapter_title': 'Chapter 2',
                'page_start': 2,
                'page_end': 2,
                'chunk_type': 'chapter'
            }
        ]
        
        prompt = build_synthesis_prompt(
            user_message="Test",
            conversation_history=[],
            chunks=chunks
        )
        
        assert "First chunk" in prompt
        assert "Second chunk" in prompt
        assert "[1]" in prompt  # Citation markers
        assert "[2]" in prompt
    
    def test_prompt_with_conversation_history(self):
        """Test prompt includes conversation history."""
        history = [
            ChatMessage(role="user", content="First question"),
            ChatMessage(role="assistant", content="First answer"),
            ChatMessage(role="user", content="Follow-up question")
        ]
        
        prompt = build_synthesis_prompt(
            user_message="Follow-up question",
            conversation_history=history,
            chunks=[]
        )
        
        assert "First question" in prompt or "Follow-up question" in prompt
    
    def test_prompt_with_session_context(self):
        """Test prompt includes session context."""
        session_context = "Focus on M&A transactions"
        
        prompt = build_synthesis_prompt(
            user_message="Test",
            conversation_history=[],
            chunks=[],
            session_context=session_context
        )
        
        assert "M&A" in prompt or "transactions" in prompt.lower()


class TestPromptSystem:
    """Test prompt registry system."""
    
    def test_get_system_prompt(self):
        """Test retrieving system prompt."""
        prompt = get_prompt("chat.system")
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "professor" in prompt.lower() or "expert" in prompt.lower()
    
    def test_get_synthesis_prompt_template(self):
        """Test retrieving synthesis prompt template."""
        prompt = get_prompt("chat.synthesis", variables={
            'context_section': '',
            'chunks_text': 'Test chunks',
            'history_text': '',
            'user_message': 'Test message'
        })
        assert isinstance(prompt, str)
        assert "Test chunks" in prompt
        assert "Test message" in prompt
    
    def test_prompt_with_missing_variable(self):
        """Test that missing variables raise error."""
        with pytest.raises(KeyError):
            get_prompt("chat.synthesis", variables={
                'chunks_text': 'Test'  # Missing required variables
            })
    
    def test_invalid_prompt_name(self):
        """Test that invalid prompt names raise error."""
        with pytest.raises(KeyError):
            get_prompt("invalid.prompt.name")


class TestChatModels:
    """Test chat model classes."""
    
    def test_chat_message_creation(self):
        """Test creating ChatMessage."""
        msg = ChatMessage(
            role="user",
            content="Test message"
        )
        assert msg.role == "user"
        assert msg.content == "Test message"
        assert msg.id is not None
        assert isinstance(msg.timestamp, datetime)
    
    def test_chat_state_creation(self):
        """Test creating ChatState."""
        state = ChatState(
            session_id="test-123",
            messages=[
                ChatMessage(role="user", content="Hello")
            ]
        )
        assert state.session_id == "test-123"
        assert len(state.messages) == 1
        assert state.status == "idle"
    
    def test_chat_state_immutable_update(self):
        """Test immutable state updates."""
        state = ChatState()
        new_msg = ChatMessage(role="user", content="New message")
        
        # Immutable update
        updated_state = state.model_copy(update={
            'messages': [*state.messages, new_msg]
        })
        
        assert len(updated_state.messages) == 1
        assert len(state.messages) == 0  # Original unchanged
