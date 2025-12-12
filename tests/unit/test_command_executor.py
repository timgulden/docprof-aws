"""
Unit tests for command executor.

Tests command execution logic with mocked AWS services.
These tests run locally and verify command routing and error handling.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, Mock

# Add Lambda source to path
lambda_path = Path(__file__).parent.parent.parent / "src" / "lambda"
sys.path.insert(0, str(lambda_path))

# Mock AWS dependencies BEFORE any imports
class MockModule:
    def __getattr__(self, name):
        return MagicMock()

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

# Now import
from shared.core.commands import (
    EmbedCommand,
    LLMCommand,
    SearchBookSummariesCommand,
    SearchCorpusCommand,
    CreateCourseCommand,
    CreateSectionsCommand,
)
from shared.command_executor import execute_command


class TestEmbedCommand:
    """Test EmbedCommand execution."""
    
    @patch('shared.command_executor.generate_embeddings')
    def test_execute_embed_command_success(self, mock_generate_embeddings):
        """Test successful embedding generation."""
        # Setup mock
        mock_embedding = [0.1] * 1536  # 1536-dimensional embedding
        mock_generate_embeddings.return_value = [mock_embedding]
        
        # Execute command
        command = EmbedCommand(text="test query", task="test_task")
        result = execute_command(command)
        
        # Verify
        assert result['status'] == 'success'
        assert 'embedding' in result
        assert result['embedding'] == mock_embedding
        assert result['task'] == "test_task"
        mock_generate_embeddings.assert_called_once_with(["test query"])
    
    @patch('shared.command_executor.generate_embeddings')
    def test_execute_embed_command_error(self, mock_generate_embeddings):
        """Test embedding generation error handling."""
        # Setup mock to raise error
        mock_generate_embeddings.side_effect = Exception("API error")
        
        # Execute command
        command = EmbedCommand(text="test query", task="test_task")
        result = execute_command(command)
        
        # Verify error handling
        assert result['status'] == 'error'
        assert 'error' in result
        assert "API error" in result['error']


class TestLLMCommand:
    """Test LLMCommand execution."""
    
    @patch('shared.command_executor.invoke_claude')
    @patch('shared.command_executor.get_prompt')
    def test_execute_llm_command_with_prompt_name(self, mock_get_prompt, mock_invoke_claude):
        """Test LLM command with prompt name."""
        # Setup mocks
        mock_get_prompt.return_value = "System prompt: {query}"
        mock_invoke_claude.return_value = {
            'content': 'Generated response',
            'usage': {'input_tokens': 100, 'output_tokens': 50}
        }
        
        # Execute command
        command = LLMCommand(
            prompt_name="test.prompt",
            prompt_variables={"query": "test"},
            task="test_task"
        )
        result = execute_command(command)
        
        # Verify
        assert result['status'] == 'success'
        assert result['content'] == 'Generated response'
        assert 'usage' in result
        mock_get_prompt.assert_called_once_with("test.prompt", {"query": "test"})
        mock_invoke_claude.assert_called_once()
    
    @patch('shared.command_executor.invoke_claude')
    def test_execute_llm_command_with_inline_prompt(self, mock_invoke_claude):
        """Test LLM command with inline prompt."""
        # Setup mock
        mock_invoke_claude.return_value = {
            'content': 'Generated response',
            'usage': {'input_tokens': 100, 'output_tokens': 50}
        }
        
        # Execute command
        command = LLMCommand(
            prompt="Inline prompt text",
            task="test_task"
        )
        result = execute_command(command)
        
        # Verify
        assert result['status'] == 'success'
        assert result['content'] == 'Generated response'
        mock_invoke_claude.assert_called_once()
    
    @patch('shared.command_executor.invoke_claude')
    def test_execute_llm_command_error(self, mock_invoke_claude):
        """Test LLM command error handling."""
        # Setup mock to raise error
        mock_invoke_claude.side_effect = Exception("Bedrock error")
        
        # Execute command
        command = LLMCommand(prompt="test prompt", task="test_task")
        result = execute_command(command)
        
        # Verify error handling
        assert result['status'] == 'error'
        assert 'error' in result


class TestSearchBookSummariesCommand:
    """Test SearchBookSummariesCommand execution."""
    
    def test_execute_search_book_summaries_command_not_implemented(self):
        """Test that book search returns empty list (not yet implemented)."""
        command = SearchBookSummariesCommand(
            query_embedding=[0.1] * 1536,
            top_k=10,
            min_similarity=0.2
        )
        result = execute_command(command)
        
        # Should return success but empty books list
        assert result['status'] == 'success'
        assert result['books'] == []
        assert result['top_k'] == 10


class TestSearchCorpusCommand:
    """Test SearchCorpusCommand execution."""
    
    @patch('shared.command_executor.generate_embeddings')
    @patch('shared.command_executor.vector_similarity_search')
    def test_execute_search_corpus_command_success(self, mock_vector_search, mock_generate_embeddings):
        """Test successful corpus search."""
        # Setup mocks
        mock_embedding = [0.1] * 1536
        mock_generate_embeddings.return_value = [mock_embedding]
        mock_vector_search.return_value = [
            {'chunk_id': 'chunk-1', 'content': 'Test content 1'},
            {'chunk_id': 'chunk-2', 'content': 'Test content 2'},
        ]
        
        # Execute command
        command = SearchCorpusCommand(
            query_text="test query",
            chunk_types=["text"],
            top_k={"text": 5}
        )
        result = execute_command(command)
        
        # Verify
        assert result['status'] == 'success'
        assert 'chunks' in result
        assert len(result['chunks']) == 2
        mock_generate_embeddings.assert_called_once_with(["test query"])
        mock_vector_search.assert_called_once()


class TestCreateCourseCommand:
    """Test CreateCourseCommand execution."""
    
    @patch('shared.command_executor.get_db_connection')
    def test_execute_create_course_command_success(self, mock_get_db_connection):
        """Test successful course creation."""
        from shared.core.course_models import Course, CoursePreferences
        from datetime import datetime
        import uuid
        
        # Setup mock database connection
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        mock_cur.fetchone.return_value = (uuid.uuid4(),)
        mock_get_db_connection.return_value.__enter__.return_value = mock_conn
        
        course = Course(
            course_id=str(uuid.uuid4()),
            user_id=str(uuid.uuid4()),
            title="Test Course",
            original_query="Test query",
            estimated_hours=2.0,
            preferences=CoursePreferences(),
        )
        
        command = CreateCourseCommand(course=course)
        result = execute_command(command)
        
        # Verify success
        assert result['status'] == 'success'
        assert 'course_id' in result
        assert 'course' in result
        
        # Verify database call
        mock_cur.execute.assert_called_once()
        # Note: commit happens in context manager __exit__, so we verify execute was called
    
    @patch('shared.command_executor.get_db_connection')
    def test_execute_create_course_command_database_error(self, mock_get_db_connection):
        """Test course creation with database error."""
        from shared.core.course_models import Course, CoursePreferences
        import uuid
        
        # Setup mock to raise error
        mock_get_db_connection.side_effect = Exception("Database connection failed")
        
        course = Course(
            course_id=str(uuid.uuid4()),
            user_id=str(uuid.uuid4()),
            title="Test Course",
            original_query="Test query",
            estimated_hours=2.0,
            preferences=CoursePreferences(),
        )
        
        command = CreateCourseCommand(course=course)
        result = execute_command(command)
        
        # Verify error handling
        assert result['status'] == 'error'
        assert 'error' in result
        assert "Database connection failed" in result['error']
    
    @patch('shared.command_executor.get_db_connection')
    def test_execute_create_course_command_with_preferences(self, mock_get_db_connection):
        """Test course creation with custom preferences."""
        from shared.core.course_models import Course, CoursePreferences
        import uuid
        
        # Setup mock database connection
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        mock_cur.fetchone.return_value = (uuid.uuid4(),)
        mock_get_db_connection.return_value.__enter__.return_value = mock_conn
        
        preferences = CoursePreferences(
            depth="technical",
            presentation_style="podcast",
            pace="thorough",
            additional_notes="Custom notes"
        )
        
        course = Course(
            course_id=str(uuid.uuid4()),
            user_id=str(uuid.uuid4()),
            title="Test Course",
            original_query="Test query",
            estimated_hours=2.0,
            preferences=preferences,
        )
        
        command = CreateCourseCommand(course=course)
        result = execute_command(command)
        
        # Verify success
        assert result['status'] == 'success'
        
        # Verify preferences were included in SQL call
        call_args = mock_cur.execute.call_args[0]
        sql = call_args[0]
        assert 'preferences' in sql.lower()


class TestCreateSectionsCommand:
    """Test CreateSectionsCommand execution."""
    
    @patch('shared.command_executor.get_db_connection')
    @patch('shared.command_executor.execute_values')
    def test_execute_create_sections_command_success(self, mock_execute_values, mock_get_db_connection):
        """Test successful section creation."""
        from shared.core.course_models import CourseSection
        import uuid
        
        # Setup mock database connection
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        mock_get_db_connection.return_value.__enter__.return_value = mock_conn
        
        course_id = str(uuid.uuid4())
        sections = [
            CourseSection(
                section_id=str(uuid.uuid4()),
                course_id=course_id,
                title="Section 1",
                order_index=0,
                estimated_minutes=30,
                learning_objectives=["Objective 1", "Objective 2"],
                chunk_ids=[str(uuid.uuid4())],
            ),
            CourseSection(
                section_id=str(uuid.uuid4()),
                course_id=course_id,
                title="Section 2",
                order_index=1,
                estimated_minutes=30,
            ),
        ]
        
        command = CreateSectionsCommand(sections=sections)
        result = execute_command(command)
        
        # Verify success
        assert result['status'] == 'success'
        assert result['sections_count'] == 2
        assert len(result['sections']) == 2
        
        # Verify batch insert was called
        mock_execute_values.assert_called_once()
        # Note: commit happens in context manager __exit__, so we verify execute_values was called
    
    @patch('shared.command_executor.get_db_connection')
    def test_execute_create_sections_command_empty_list(self, mock_get_db_connection):
        """Test section creation with empty list."""
        command = CreateSectionsCommand(sections=[])
        result = execute_command(command)
        
        # Should return success with 0 sections
        assert result['status'] == 'success'
        assert result['sections_count'] == 0
        assert result['sections'] == []
        
        # Should not call database
        mock_get_db_connection.assert_not_called()
    
    @patch('shared.command_executor.get_db_connection')
    @patch('shared.command_executor.execute_values')
    def test_execute_create_sections_command_with_hierarchy(self, mock_execute_values, mock_get_db_connection):
        """Test section creation with parent-child hierarchy."""
        from shared.core.course_models import CourseSection
        import uuid
        
        # Setup mock database connection
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        mock_get_db_connection.return_value.__enter__.return_value = mock_conn
        
        course_id = str(uuid.uuid4())
        parent_id = str(uuid.uuid4())
        
        sections = [
            CourseSection(
                section_id=parent_id,
                course_id=course_id,
                title="Part 1",
                order_index=0,
                estimated_minutes=60,
                parent_section_id=None,  # Top-level part
            ),
            CourseSection(
                section_id=str(uuid.uuid4()),
                course_id=course_id,
                title="Section 1.1",
                order_index=1,
                estimated_minutes=30,
                parent_section_id=parent_id,  # Child of Part 1
            ),
        ]
        
        command = CreateSectionsCommand(sections=sections)
        result = execute_command(command)
        
        # Verify success
        assert result['status'] == 'success'
        assert result['sections_count'] == 2
        
        # Verify batch insert was called with both sections
        mock_execute_values.assert_called_once()
        call_args = mock_execute_values.call_args
        values = call_args[0][2]  # Third argument is values
        assert len(values) == 2
    
    @patch('shared.command_executor.get_db_connection')
    def test_execute_create_sections_command_database_error(self, mock_get_db_connection):
        """Test section creation with database error."""
        from shared.core.course_models import CourseSection
        import uuid
        
        # Setup mock to raise error
        mock_get_db_connection.side_effect = Exception("Database error")
        
        sections = [
            CourseSection(
                section_id=str(uuid.uuid4()),
                course_id=str(uuid.uuid4()),
                title="Section 1",
                order_index=0,
                estimated_minutes=30,
            ),
        ]
        
        command = CreateSectionsCommand(sections=sections)
        result = execute_command(command)
        
        # Verify error handling
        assert result['status'] == 'error'
        assert 'error' in result
        assert "Database error" in result['error']
