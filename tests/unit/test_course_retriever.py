"""
Unit tests for course retriever Lambda handler.

Tests course retrieval logic with mocked database.
"""

import pytest
import sys
import json
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch, Mock
from datetime import datetime

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
from course_retriever.handler import lambda_handler


class TestCourseRetriever:
    """Test course retriever Lambda handler."""
    
    @patch('course_retriever.handler.get_db_connection')
    def test_retrieve_course_success(self, mock_get_db_connection):
        """Test successful course retrieval."""
        course_id = uuid.uuid4()
        user_id = uuid.uuid4()
        
        # Setup mock database connection
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        mock_get_db_connection.return_value.__enter__.return_value = mock_conn
        
        # Mock course query result
        preferences_json = json.dumps({
            "depth": "balanced",
            "presentation_style": "conversational",
            "pace": "moderate",
            "additional_notes": ""
        })
        
        mock_cur.fetchone.side_effect = [
            # Course row
            (
                course_id,
                user_id,
                "Test Course",
                "Test query",
                2.0,
                datetime(2024, 1, 1),
                datetime(2024, 1, 2),
                preferences_json,
                "active"
            ),
        ]
        
        # Mock sections query result
        section_id_1 = uuid.uuid4()
        section_id_2 = uuid.uuid4()
        mock_cur.fetchall.return_value = [
            (
                section_id_1,
                course_id,
                None,  # parent_section_id
                0,  # order_index
                "Section 1",
                ["Objective 1", "Objective 2"],  # learning_objectives
                "Summary 1",
                30,  # estimated_minutes
                [uuid.uuid4()],  # chunk_ids
                "not_started",
                None,  # completed_at
                False,  # can_standalone
                [],  # prerequisites
                datetime(2024, 1, 1),  # created_at
            ),
            (
                section_id_2,
                course_id,
                None,
                1,
                "Section 2",
                [],
                None,
                30,
                [],
                "not_started",
                None,
                False,
                [],
                datetime(2024, 1, 1),
            ),
        ]
        
        # Create event
        event = {
            'pathParameters': {'courseId': str(course_id)},
            'queryStringParameters': None
        }
        
        result = lambda_handler(event, None)
        
        # Verify response
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert 'course' in body
        assert 'sections' in body
        assert body['section_count'] == 2
        
        # Verify course data
        assert body['course']['course_id'] == str(course_id)
        assert body['course']['title'] == "Test Course"
        assert body['course']['estimated_hours'] == 2.0
        
        # Verify sections
        assert len(body['sections']) == 2
        assert body['sections'][0]['title'] == "Section 1"
        assert body['sections'][0]['learning_objectives'] == ["Objective 1", "Objective 2"]
        assert body['sections'][1]['title'] == "Section 2"
    
    @patch('course_retriever.handler.get_db_connection')
    def test_retrieve_course_not_found(self, mock_get_db_connection):
        """Test course retrieval when course doesn't exist."""
        course_id = uuid.uuid4()
        
        # Setup mock database connection
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        mock_get_db_connection.return_value.__enter__.return_value = mock_conn
        
        # Mock course query returns None (not found)
        mock_cur.fetchone.return_value = None
        
        event = {
            'pathParameters': {'courseId': str(course_id)},
            'queryStringParameters': None
        }
        
        result = lambda_handler(event, None)
        
        # Verify 404 response
        assert result['statusCode'] == 404
        body = json.loads(result['body'])
        assert 'error' in body
        assert "not found" in body['error'].lower()
    
    def test_retrieve_course_missing_course_id(self):
        """Test course retrieval with missing courseId."""
        event = {
            'pathParameters': {},
            'queryStringParameters': None
        }
        
        result = lambda_handler(event, None)
        
        # Verify 400 response
        assert result['statusCode'] == 400
        body = json.loads(result['body'])
        assert 'error' in body
        assert "missing" in body['error'].lower()
    
    def test_retrieve_course_invalid_uuid(self):
        """Test course retrieval with invalid UUID."""
        event = {
            'pathParameters': {'courseId': 'not-a-uuid'},
            'queryStringParameters': None
        }
        
        result = lambda_handler(event, None)
        
        # Verify 400 response
        assert result['statusCode'] == 400
        body = json.loads(result['body'])
        assert 'error' in body
        assert "invalid" in body['error'].lower()
    
    @patch('course_retriever.handler.get_db_connection')
    def test_retrieve_course_with_query_string(self, mock_get_db_connection):
        """Test course retrieval using query string parameter."""
        course_id = uuid.uuid4()
        user_id = uuid.uuid4()
        
        # Setup mock database connection
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        mock_get_db_connection.return_value.__enter__.return_value = mock_conn
        
        preferences_json = json.dumps({
            "depth": "balanced",
            "presentation_style": "conversational",
            "pace": "moderate",
            "additional_notes": ""
        })
        
        mock_cur.fetchone.return_value = (
            course_id, user_id, "Test Course", "Test query",
            2.0, datetime(2024, 1, 1), datetime(2024, 1, 2),
            preferences_json, "active"
        )
        mock_cur.fetchall.return_value = []
        
        # Use query string instead of path parameter
        event = {
            'pathParameters': None,
            'queryStringParameters': {'courseId': str(course_id)}
        }
        
        result = lambda_handler(event, None)
        
        # Verify success
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['course']['course_id'] == str(course_id)
    
    @patch('course_retriever.handler.get_db_connection')
    def test_retrieve_course_with_sections_hierarchy(self, mock_get_db_connection):
        """Test course retrieval with hierarchical sections (parts → sections)."""
        course_id = uuid.uuid4()
        user_id = uuid.uuid4()
        part_id = uuid.uuid4()
        section_id = uuid.uuid4()
        
        # Setup mock database connection
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        mock_get_db_connection.return_value.__enter__.return_value = mock_conn
        
        preferences_json = json.dumps({
            "depth": "balanced",
            "presentation_style": "conversational",
            "pace": "moderate",
            "additional_notes": ""
        })
        
        mock_cur.fetchone.return_value = (
            course_id, user_id, "Test Course", "Test query",
            2.0, datetime(2024, 1, 1), datetime(2024, 1, 2),
            preferences_json, "active"
        )
        
        # Mock sections with hierarchy
        mock_cur.fetchall.return_value = [
            (
                part_id,
                course_id,
                None,  # parent_section_id (top-level part)
                0,
                "Part 1",
                [],
                None,
                60,
                [],
                "not_started",
                None,
                False,
                [],
                datetime(2024, 1, 1),
            ),
            (
                section_id,
                course_id,
                part_id,  # parent_section_id (child of Part 1)
                1,
                "Section 1.1",
                [],
                None,
                30,
                [],
                "not_started",
                None,
                False,
                [],
                datetime(2024, 1, 1),
            ),
        ]
        
        event = {
            'pathParameters': {'courseId': str(course_id)},
            'queryStringParameters': None
        }
        
        result = lambda_handler(event, None)
        
        # Verify response
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        
        # Verify hierarchy
        assert len(body['sections']) == 2
        assert body['sections'][0]['parent_section_id'] is None  # Part
        assert body['sections'][1]['parent_section_id'] == str(part_id)  # Child section
    
    @patch('course_retriever.handler.get_db_connection')
    def test_retrieve_course_database_error(self, mock_get_db_connection):
        """Test course retrieval with database error."""
        course_id = uuid.uuid4()
        
        # Setup mock to raise error
        mock_get_db_connection.side_effect = Exception("Database connection failed")
        
        event = {
            'pathParameters': {'courseId': str(course_id)},
            'queryStringParameters': None
        }
        
        result = lambda_handler(event, None)
        
        # Verify 500 response
        assert result['statusCode'] == 500
        body = json.loads(result['body'])
        assert 'error' in body
        assert "Failed to retrieve course" in body['error']
