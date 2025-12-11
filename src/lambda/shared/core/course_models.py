from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Set
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


# Course preference types
CourseDepth = Literal["overview", "balanced", "technical", "expert"]
CoursePace = Literal["quick", "moderate", "thorough"]
CourseStatus = Literal["active", "completed", "archived"]
SectionStatus = Literal["not_started", "in_progress", "completed"]


class CoursePreferences(BaseModel):
    """User preferences for course delivery style."""

    model_config = ConfigDict(frozen=True)

    depth: CourseDepth = "balanced"
    presentation_style: str = "conversational"  # Can be simple keyword or detailed description
    pace: CoursePace = "moderate"
    additional_notes: str = ""


class Course(BaseModel):
    """Course model representing a user's learning path."""

    model_config = ConfigDict(frozen=False)

    course_id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    title: str
    original_query: str  # What user asked for
    estimated_hours: float
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_modified: datetime = Field(default_factory=datetime.utcnow)
    preferences: CoursePreferences = Field(default_factory=lambda: CoursePreferences())
    status: CourseStatus = "active"


class CourseSection(BaseModel):
    """A section within a course outline."""

    model_config = ConfigDict(frozen=False)

    section_id: str = Field(default_factory=lambda: str(uuid4()))
    course_id: str
    parent_section_id: Optional[str] = None  # For hierarchical structure
    order_index: int
    title: str
    learning_objectives: List[str] = Field(default_factory=list)
    content_summary: Optional[str] = None
    estimated_minutes: int
    chunk_ids: List[str] = Field(default_factory=list)  # Relevant source chunks
    status: SectionStatus = "not_started"
    completed_at: Optional[datetime] = None
    can_standalone: bool = False
    prerequisites: List[str] = Field(default_factory=list)  # section_ids
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SectionDelivery(BaseModel):
    """Generated lecture content for a section."""

    model_config = ConfigDict(frozen=False)

    delivery_id: str = Field(default_factory=lambda: str(uuid4()))
    section_id: str
    user_id: str
    lecture_script: str
    delivered_at: datetime = Field(default_factory=datetime.utcnow)
    duration_actual_minutes: Optional[int] = None
    user_notes: Optional[str] = None
    style_snapshot: Dict[str, Any] = Field(default_factory=dict)  # Preferences at delivery time
    audio_data: Optional[bytes] = None  # Generated audio (MP3 format) - optional


class QAMessage(BaseModel):
    """A single message in a Q&A session."""

    model_config = ConfigDict(frozen=True)

    role: Literal["user", "assistant"]
    content: str
    timestamp: str  # ISO format string


class QASession(BaseModel):
    """Q&A session during section delivery."""

    model_config = ConfigDict(frozen=False)

    qa_session_id: str = Field(default_factory=lambda: str(uuid4()))
    section_id: str
    delivery_id: Optional[str] = None
    user_id: str
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None
    lecture_position_seconds: Optional[int] = None  # Where lecture was paused
    qa_messages: List[QAMessage] = Field(default_factory=list)
    context_chunks: List[str] = Field(default_factory=list)  # Chunks used in answers
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CourseHistoryEntry(BaseModel):
    """A single entry in course modification history."""

    model_config = ConfigDict(frozen=True)

    history_id: str
    course_id: str
    change_type: str  # 'created', 'expanded', 'compressed', 'section_added', 'preference_updated', 'outline_modified'
    change_description: str
    outline_snapshot: Optional[Dict[str, Any]] = None
    timestamp: datetime


# Course State Management (similar to ChatState)
CourseDeliveryMode = Literal["lecture", "qa"]


class CourseState(BaseModel):
    """Top-level course state for managing course interactions."""

    model_config = ConfigDict(frozen=False)

    session_id: Optional[str] = None
    current_course: Optional[Course] = None
    current_section: Optional[CourseSection] = None
    current_delivery: Optional[SectionDelivery] = None
    current_qa_session: Optional[QASession] = None
    section_delivery_mode: Optional[CourseDeliveryMode] = None  # 'lecture' or 'qa'
    lecture_pause_position: Optional[int] = None  # Seconds into lecture
    
    # Pending course creation fields
    pending_course_query: Optional[str] = None
    pending_course_hours: Optional[float] = None
    pending_course_prefs: Optional[CoursePreferences] = None
    
    # Pending Q&A fields
    pending_qa_question: Optional[str] = None
    
    # Helper fields for logic flow
    standalone_request_minutes: Optional[int] = None
    pending_corpus_search: bool = False
    pending_book_search: bool = False  # For book summary search
    pending_outline_generation: bool = False
    pending_next_section_query: bool = False
    pending_lecture_generation: bool = False
    
    # Section lecture generation fields (objective-by-objective)
    current_section_draft: Optional[str] = None  # Accumulating lecture content during generation
    covered_objectives: List[int] = Field(default_factory=list)  # Indices of covered objectives (0-based)
    section_generation_phase: Literal["objectives", "refining", "complete"] = "objectives"
    previous_lectures_context: Optional[str] = None  # Formatted previous section lectures
    course_outline_context: Optional[str] = None  # Formatted course outline
    selected_lecture_figures: List[Dict[str, Any]] = Field(default_factory=list)  # Selected figures for current lecture (0-3)
    
    # Multi-phase outline generation fields
    outline_text: Optional[str] = None  # Intermediate text outline (not in DB yet)
    parts_list: List[Dict[str, Any]] = Field(default_factory=list)  # [{title, minutes}, ...]
    current_part_index: int = 0  # Which part we're expanding (0-based)
    outline_complete: bool = False  # All parts expanded, ready for review/parsing
    book_summaries_json: Optional[str] = None  # JSON string of book summaries for Phase 2-N
    
    # Outline revision fields
    pending_revision_course_id: Optional[str] = None
    pending_revision_request: Optional[str] = None
    pending_revision_completed_section_ids: Optional[Set[str]] = Field(default=None)  # Completed section IDs to preserve
    pending_revision_new_sections: Optional[List["CourseSection"]] = None  # New sections to create during revision
    is_revision: bool = False  # Flag to indicate this is a revision (not a new course)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    ui_message: Optional[str] = None


class CourseStateSnapshot(BaseModel):
    """Serializable snapshot of course state for persistence."""

    model_config = ConfigDict(frozen=True)

    session_id: Optional[str]
    current_course: Optional[Course]
    current_section: Optional[CourseSection]
    current_delivery: Optional[SectionDelivery]
    current_qa_session: Optional[QASession]
    section_delivery_mode: Optional[CourseDeliveryMode]
    lecture_pause_position: Optional[int]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_state(cls, state: CourseState) -> "CourseStateSnapshot":
        """Create snapshot from CourseState."""
        return cls(
            session_id=state.session_id,
            current_course=state.current_course.model_copy(deep=True) if state.current_course else None,
            current_section=state.current_section.model_copy(deep=True) if state.current_section else None,
            current_delivery=state.current_delivery.model_copy(deep=True) if state.current_delivery else None,
            current_qa_session=state.current_qa_session.model_copy(deep=True) if state.current_qa_session else None,
            section_delivery_mode=state.section_delivery_mode,
            lecture_pause_position=state.lecture_pause_position,
            created_at=state.created_at,
            updated_at=state.updated_at,
        )

