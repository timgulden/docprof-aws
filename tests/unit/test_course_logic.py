"""
Unit tests for course logic functions.

Tests pure logic functions for course generation workflow.
These tests run locally and require no AWS infrastructure.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock

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
from shared.logic.courses import (
    create_initial_course_state,
    request_course,
    parse_parts_text,
    parse_outline_total_time,
)
from shared.core.course_models import CourseState, CoursePreferences
from shared.core.course_events import CourseRequestedEvent


class TestCreateInitialCourseState:
    """Test create_initial_course_state function."""
    
    def test_creates_empty_state(self):
        """Test that initial state is empty."""
        state = create_initial_course_state()
        
        assert isinstance(state, CourseState)
        assert state.session_id is None
        assert state.pending_course_query is None
        assert state.parts_list == []
        assert state.current_part_index == 0
        assert state.outline_complete is False


class TestRequestCourse:
    """Test request_course function."""
    
    def test_request_course_creates_state(self):
        """Test that request_course sets up state correctly."""
        state = create_initial_course_state()
        state.session_id = "test-course-123"
        
        prefs = CoursePreferences(difficulty_level="intermediate")
        result = request_course(
            state=state,
            query="Learn DCF valuation",
            time_hours=2.0,
            preferences=prefs
        )
        
        # Verify state updated
        assert result.new_state.pending_course_query == "Learn DCF valuation"
        assert result.new_state.pending_course_hours == 2.0
        assert result.new_state.pending_course_prefs == prefs
        
        # Verify command emitted
        assert len(result.commands) > 0
        from shared.core.commands import EmbedCommand
        assert isinstance(result.commands[0], EmbedCommand)
        assert result.commands[0].text == "Learn DCF valuation"
    
    def test_request_course_without_preferences(self):
        """Test request_course without preferences."""
        state = create_initial_course_state()
        state.session_id = "test-course-123"
        
        result = request_course(
            state=state,
            query="Learn DCF valuation",
            time_hours=2.0,
            preferences=None
        )
        
        # Should create default preferences
        assert result.new_state.pending_course_prefs is not None
        assert isinstance(result.new_state.pending_course_prefs, CoursePreferences)


class TestParsePartsText:
    """Test parse_parts_text function."""
    
    def test_parse_simple_parts(self):
        """Test parsing simple parts text."""
        parts_text = """
Part 1: Introduction - 30 minutes
Part 2: Advanced Topics - 90 minutes
Total: 120 minutes
"""
        parts = parse_parts_text(parts_text, target_minutes=120)
        
        assert len(parts) == 2
        assert parts[0]['title'] == "Introduction"
        assert parts[0]['minutes'] == 30
        assert parts[1]['title'] == "Advanced Topics"
        assert parts[1]['minutes'] == 90
    
    def test_parse_parts_with_variations(self):
        """Test parsing parts with different formats."""
        parts_text = """
Part 1: Introduction to Valuation - 30 minutes
Part 2: DCF Modeling - 60 minutes
Part 3: Advanced Techniques - 30 minutes
"""
        parts = parse_parts_text(parts_text, target_minutes=120)
        
        assert len(parts) == 3
        assert sum(p['minutes'] for p in parts) == 120
    
    def test_parse_parts_ignores_total_line(self):
        """Test that total line is ignored."""
        parts_text = """
Part 1: Introduction - 30 minutes
Total: 30 minutes
"""
        parts = parse_parts_text(parts_text, target_minutes=30)
        
        assert len(parts) == 1
        assert parts[0]['minutes'] == 30
    
    def test_parse_parts_handles_empty_text(self):
        """Test parsing empty text."""
        parts = parse_parts_text("", target_minutes=120)
        
        assert len(parts) == 0
    
    def test_parse_parts_validates_total(self):
        """Test that parsing validates total time."""
        # This should parse but log warning if total doesn't match
        parts_text = """
Part 1: Introduction - 30 minutes
Part 2: Advanced - 60 minutes
"""
        parts = parse_parts_text(parts_text, target_minutes=120)
        
        # Should still parse even if total doesn't match exactly
        assert len(parts) == 2
        assert sum(p['minutes'] for p in parts) == 90


class TestParseOutlineTotalTime:
    """Test parse_outline_total_time function."""
    
    def test_parse_time_from_sections(self):
        """Test parsing time from section markers."""
        outline_text = """
### Section 1: Introduction - 15 minutes
### Section 2: Basics - 20 minutes
### Section 3: Advanced - 25 minutes
"""
        total = parse_outline_total_time(outline_text)
        
        assert total == 60
    
    def test_parse_time_from_part_totals(self):
        """Test parsing time from part totals."""
        outline_text = """
Part 1: Introduction
### Section 1: Basics - 20 minutes
Total for this part: 20 minutes
"""
        total = parse_outline_total_time(outline_text)
        
        assert total == 20
    
    def test_parse_time_from_final_total(self):
        """Test parsing time from final total."""
        outline_text = """
Part 1: Introduction
Section 1: Basics
Section 2: Advanced
Total: 120 minutes
"""
        total = parse_outline_total_time(outline_text)
        
        assert total == 120
    
    def test_parse_time_handles_empty_text(self):
        """Test parsing empty outline."""
        total = parse_outline_total_time("")
        
        assert total == 0
    
    def test_parse_time_handles_no_time_markers(self):
        """Test parsing outline with no time markers."""
        outline_text = """
Part 1: Introduction
Section 1: Basics
Section 2: Advanced
"""
        total = parse_outline_total_time(outline_text)
        
        assert total == 0
