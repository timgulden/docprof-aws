"""
Unit tests for course state manager.

Tests DynamoDB serialization/deserialization of CourseState.
These tests run locally with mocked DynamoDB.
"""

import pytest
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

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
from shared.core.course_models import CourseState, CoursePreferences, Course, CourseSection
from shared.course_state_manager import (
    course_state_to_dict,
    dict_to_course_state,
)


class TestCourseStateSerialization:
    """Test CourseState serialization to/from DynamoDB dict."""
    
    def test_empty_state_serialization(self):
        """Test serializing empty CourseState."""
        state = CourseState()
        state_dict = course_state_to_dict(state)
        
        assert 'course_id' in state_dict
        assert state_dict['course_id'] == ''  # Empty session_id
        assert 'pending_course_query' in state_dict
        assert 'pending_course_hours' in state_dict
        assert 'parts_list' in state_dict
        assert 'current_part_index' in state_dict
        assert 'outline_text' in state_dict
        assert 'outline_complete' in state_dict
        assert 'ttl' in state_dict
    
    def test_state_with_query_serialization(self):
        """Test serializing CourseState with query."""
        state = CourseState(
            session_id="test-course-123",
            pending_course_query="Learn DCF valuation",
            pending_course_hours=2.0,
        )
        state_dict = course_state_to_dict(state)
        
        assert state_dict['course_id'] == "test-course-123"
        assert state_dict['pending_course_query'] == "Learn DCF valuation"
        assert state_dict['pending_course_hours'] == 2.0
    
    def test_state_with_preferences_serialization(self):
        """Test serializing CourseState with preferences."""
        prefs = CoursePreferences(
            depth="technical",
            presentation_style="detailed",
            pace="thorough",
            additional_notes="Focus on practical examples"
        )
        state = CourseState(
            session_id="test-course-123",
            pending_course_prefs=prefs,
        )
        state_dict = course_state_to_dict(state)
        
        assert 'pending_course_prefs' in state_dict
        assert isinstance(state_dict['pending_course_prefs'], dict)
        assert state_dict['pending_course_prefs']['depth'] == "technical"
        assert state_dict['pending_course_prefs']['presentation_style'] == "detailed"
        assert state_dict['pending_course_prefs']['pace'] == "thorough"
    
    def test_state_with_parts_serialization(self):
        """Test serializing CourseState with parts list."""
        parts_list = [
            {"title": "Part 1: Introduction", "minutes": 30},
            {"title": "Part 2: Advanced Topics", "minutes": 90},
        ]
        state = CourseState(
            session_id="test-course-123",
            parts_list=parts_list,
            current_part_index=1,
        )
        state_dict = course_state_to_dict(state)
        
        assert state_dict['parts_list'] == parts_list
        assert state_dict['current_part_index'] == 1
    
    def test_state_with_outline_serialization(self):
        """Test serializing CourseState with outline text."""
        outline_text = "Part 1: Introduction\nSection 1: Basics\nSection 2: Advanced"
        state = CourseState(
            session_id="test-course-123",
            outline_text=outline_text,
            outline_complete=True,
        )
        state_dict = course_state_to_dict(state)
        
        assert state_dict['outline_text'] == outline_text
        assert state_dict['outline_complete'] is True
    
    def test_round_trip_serialization(self):
        """Test that serialization and deserialization preserves all fields."""
        original_state = CourseState(
            session_id="test-course-123",
            pending_course_query="Learn DCF valuation",
            pending_course_hours=2.5,
            pending_course_prefs=CoursePreferences(
                depth="balanced",
                presentation_style="conversational",
                pace="moderate"
            ),
            parts_list=[
                {"title": "Part 1", "minutes": 60},
                {"title": "Part 2", "minutes": 90},
            ],
            current_part_index=0,
            outline_text="Part 1: Introduction\nSection 1: Basics",
            outline_complete=False,
            book_summaries_json='[{"book_id": "123", "title": "Test Book"}]',
        )
        
        # Serialize
        state_dict = course_state_to_dict(original_state)
        
        # Deserialize
        restored_state = dict_to_course_state(state_dict)
        
        # Verify all fields preserved
        assert restored_state.session_id == original_state.session_id
        assert restored_state.pending_course_query == original_state.pending_course_query
        assert restored_state.pending_course_hours == original_state.pending_course_hours
        assert restored_state.parts_list == original_state.parts_list
        assert restored_state.current_part_index == original_state.current_part_index
        assert restored_state.outline_text == original_state.outline_text
        assert restored_state.outline_complete == original_state.outline_complete
        assert restored_state.book_summaries_json == original_state.book_summaries_json
        
        # Verify preferences
        assert restored_state.pending_course_prefs is not None
        assert restored_state.pending_course_prefs.depth == "balanced"
        assert restored_state.pending_course_prefs.presentation_style == "conversational"
        assert restored_state.pending_course_prefs.pace == "moderate"
    
    def test_deserialization_with_missing_fields(self):
        """Test deserialization handles missing optional fields."""
        state_dict = {
            'course_id': 'test-course-123',
            'pending_course_query': 'Test query',
            'pending_course_hours': 2.0,
            'parts_list': [],
            'current_part_index': 0,
            'outline_text': '',
            'outline_complete': False,
        }
        
        state = dict_to_course_state(state_dict)
        
        assert state.session_id == 'test-course-123'
        assert state.pending_course_query == 'Test query'
        assert state.parts_list == []
        # Optional fields should use defaults
        assert state.pending_course_prefs is None or isinstance(state.pending_course_prefs, CoursePreferences)
    
    def test_serialization_preserves_nested_models(self):
        """Test that nested Course and CourseSection models are preserved."""
        # Create a course with sections
        course = Course(
            course_id="course-123",
            user_id="user-456",
            title="Test Course",
            original_query="Test query",
            estimated_hours=2.0,
        )
        
        section = CourseSection(
            section_id="section-789",
            course_id="course-123",
            title="Test Section",
            order_index=0,
            estimated_minutes=30,
        )
        
        state = CourseState(
            session_id="test-course-123",
            current_course=course,
            current_section=section,
        )
        
        state_dict = course_state_to_dict(state)
        
        assert 'current_course' in state_dict
        assert isinstance(state_dict['current_course'], dict)
        assert state_dict['current_course']['course_id'] == "course-123"
        assert state_dict['current_course']['title'] == "Test Course"
        
        assert 'current_section' in state_dict
        assert isinstance(state_dict['current_section'], dict)
        assert state_dict['current_section']['section_id'] == "section-789"
        
        # Round trip
        restored_state = dict_to_course_state(state_dict)
        assert restored_state.current_course is not None
        assert restored_state.current_course.course_id == "course-123"
        assert restored_state.current_section is not None
        assert restored_state.current_section.section_id == "section-789"
