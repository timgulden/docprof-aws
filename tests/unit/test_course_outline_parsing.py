"""
Unit test for course outline parsing.

Tests the parse_text_outline_to_database function with realistic outline text
to ensure sections are correctly parsed and commands are generated.
"""

import sys
import os
from pathlib import Path

# Add shared code to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src" / "lambda"))

from shared.logic.courses import parse_text_outline_to_database
from shared.core.course_models import CourseState, CoursePreferences
from shared.core.commands import CreateCourseCommand, CreateSectionsCommand, RecordCourseHistoryCommand


# Sample outline text similar to what LLM generates
SAMPLE_OUTLINE = """## Part 1: Introduction to DCF Valuation

### Section 1: Understanding Discounted Cash Flow - 15 minutes
Learning objectives:
- Define DCF and its purpose in valuation
- Explain the time value of money concept
- Identify the key components of DCF analysis

### Section 2: Free Cash Flow Fundamentals - 20 minutes
Learning objectives:
- Calculate unlevered free cash flow
- Understand the difference between FCFF and FCFE
- Recognize common adjustments to cash flow

### Section 3: Terminal Value Calculation - 25 minutes
Learning objectives:
- Apply the perpetuity growth method
- Use exit multiple approach for terminal value
- Compare and contrast different terminal value methods

Total for this part: 60 minutes

## Part 2: Advanced DCF Techniques

### Section 4: Discount Rate Selection - 20 minutes
Learning objectives:
- Calculate weighted average cost of capital (WACC)
- Determine appropriate risk-free rate and equity risk premium
- Adjust discount rates for company-specific risks

### Section 5: Sensitivity Analysis - 25 minutes
Learning objectives:
- Build sensitivity tables for key assumptions
- Interpret results and identify value drivers
- Communicate uncertainty to stakeholders

### Section 6: Scenario Modeling - 15 minutes
Learning objectives:
- Create base, bull, and bear case scenarios
- Weight probability of different outcomes
- Present range of valuations to decision-makers

Total for this part: 60 minutes

Total: 120 minutes
"""


def test_parse_outline_text():
    """Test that outline text is correctly parsed into parts and sections."""
    # Create state with outline text and required fields
    state = CourseState(
        session_id="test-course-123",
        user_id="test-user-456",  # Now required in state
        pending_course_query="Learn DCF valuation",
        pending_course_hours=2.0,
        pending_course_prefs=CoursePreferences(),
        outline_text=SAMPLE_OUTLINE,
        outline_complete=True,
    )
    
    # Call parsing function
    result = parse_text_outline_to_database(state)
    
    # Verify commands were generated
    assert len(result.commands) == 3, f"Expected 3 commands, got {len(result.commands)}"
    assert isinstance(result.commands[0], CreateCourseCommand), "First command should be CreateCourseCommand"
    assert isinstance(result.commands[1], CreateSectionsCommand), "Second command should be CreateSectionsCommand"
    assert isinstance(result.commands[2], RecordCourseHistoryCommand), "Third command should be RecordCourseHistoryCommand"
    
    # Verify course details
    course = result.commands[0].course
    assert course.course_id == "test-course-123"
    assert course.user_id == "test-user-456"
    assert "DCF" in course.title or "Discounted" in course.title, f"Course title should reference DCF, got: {course.title}"
    assert course.estimated_hours == 2.0
    
    # Verify sections
    sections = result.commands[1].sections
    assert len(sections) > 0, "Should have parsed at least some sections"
    
    # Should have 2 parts (top-level) + 6 child sections = 8 total sections
    expected_sections = 8
    assert len(sections) == expected_sections, f"Expected {expected_sections} sections (2 parts + 6 children), got {len(sections)}"
    
    # Check first part (top-level)
    part1 = sections[0]
    assert part1.parent_section_id is None, "First section should be top-level (Part 1)"
    assert "Introduction" in part1.title, f"Part 1 title should contain 'Introduction', got: {part1.title}"
    assert part1.estimated_minutes == 60, f"Part 1 should be 60 minutes, got: {part1.estimated_minutes}"
    
    # Check first child section
    section1 = sections[1]
    assert section1.parent_section_id == part1.section_id, "Section 1 should be child of Part 1"
    assert "Understanding" in section1.title or "DCF" in section1.title, f"Section 1 title unexpected: {section1.title}"
    assert section1.estimated_minutes == 15, f"Section 1 should be 15 minutes, got: {section1.estimated_minutes}"
    assert len(section1.learning_objectives) == 3, f"Section 1 should have 3 objectives, got {len(section1.learning_objectives)}"
    
    # Check second part (top-level)
    part2 = sections[4]  # After part1 (0) and its 3 children (1,2,3)
    assert part2.parent_section_id is None, "Fifth section should be top-level (Part 2)"
    assert "Advanced" in part2.title, f"Part 2 title should contain 'Advanced', got: {part2.title}"
    assert part2.estimated_minutes == 60, f"Part 2 should be 60 minutes, got: {part2.estimated_minutes}"
    
    # Verify all sections have valid course_id
    for section in sections:
        assert section.course_id == "test-course-123", f"Section should have course_id, got: {section.course_id}"
    
    # Verify order indices are sequential
    for i, section in enumerate(sections):
        assert section.order_index == i + 1, f"Section {i} should have order_index {i+1}, got: {section.order_index}"
    
    print(f"✅ Test passed! Parsed {len(sections)} sections from outline.")
    print(f"   Course title: {course.title}")
    print(f"   Part 1: {part1.title} ({part1.estimated_minutes} min)")
    print(f"   Part 2: {part2.title} ({part2.estimated_minutes} min)")


def test_parse_empty_outline():
    """Test that empty outline returns error."""
    state = CourseState(
        session_id="test-course-123",
        user_id="test-user-456",
        pending_course_query="Learn DCF valuation",
        pending_course_hours=2.0,
        outline_text="",  # Empty!
    )
    
    result = parse_text_outline_to_database(state)
    
    # Should return no commands and error message
    assert len(result.commands) == 0, "Empty outline should return no commands"
    assert "Error" in result.ui_message, f"Should return error message, got: {result.ui_message}"
    
    print("✅ Test passed! Empty outline handled correctly.")


def test_parse_malformed_outline():
    """Test that malformed outline is handled gracefully."""
    malformed_outline = """
This is not a properly formatted outline.
It has no parts or sections.
Just random text.
    """
    
    state = CourseState(
        session_id="test-course-123",
        user_id="test-user-456",
        pending_course_query="Learn DCF valuation",
        pending_course_hours=2.0,
        outline_text=malformed_outline,
    )
    
    result = parse_text_outline_to_database(state)
    
    # Should return no commands and error message
    assert len(result.commands) == 0, "Malformed outline should return no commands"
    assert "Error" in result.ui_message, f"Should return error message, got: {result.ui_message}"
    
    print("✅ Test passed! Malformed outline handled correctly.")


def test_parse_missing_user_id():
    """Test that missing user_id returns error."""
    state = CourseState(
        session_id="test-course-123",
        user_id=None,  # Missing!
        pending_course_query="Learn DCF valuation",
        pending_course_hours=2.0,
        outline_text=SAMPLE_OUTLINE,
    )
    
    result = parse_text_outline_to_database(state)
    
    # Should return no commands and error message
    assert len(result.commands) == 0, "Missing user_id should return no commands"
    assert "Error" in result.ui_message, f"Should return error message, got: {result.ui_message}"
    assert "user" in result.ui_message.lower(), "Error message should mention user"
    
    print("✅ Test passed! Missing user_id handled correctly.")


if __name__ == "__main__":
    print("Running course outline parsing tests...\n")
    
    test_parse_outline_text()
    print()
    
    test_parse_empty_outline()
    print()
    
    test_parse_malformed_outline()
    print()
    
    test_parse_missing_user_id()
    print()
    
    print("=" * 60)
    print("All tests passed! ✨")

