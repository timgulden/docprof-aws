from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from shared.core.chat_models import BackendChatPayload, ChatStateSnapshot


class Command(BaseModel):
    """Marker base class for commands emitted by the logic layer."""

    model_config = ConfigDict(frozen=True)

    @property
    def command_name(self) -> str:
        return self.__class__.__name__


class RunIngestionPipelineCommand(Command):
    """Execute the ingestion pipeline for a single PDF textbook."""

    pdf_path: Path
    book_metadata: Dict[str, Any]
    run_id: str
    rebuild: bool = False
    skip_figures: bool = False


class UpdateIngestionMetricsCommand(Command):
    """Persist final ingestion metrics back into the datastore."""

    run_id: str
    book_id: Optional[str] = None
    total_chunks: int = 0
    total_figures: int = 0
    status: Literal["success", "failed"] = Field(default="success")
    error_message: Optional[str] = None


class SearchCorpusCommand(Command):
    """Execute a corpus search with embedding and metadata filters."""

    query_text: str
    chunk_types: List[str]
    top_k: Dict[str, int] = Field(default_factory=dict)
    metadata_filters: Dict[str, Any] = Field(default_factory=dict)
    exclude_filters: Dict[str, Any] = Field(default_factory=dict)
    return_segments: bool = False
    highlight_radius: int = 200
    include_scores: bool = True


class SearchBookSummariesCommand(Command):
    """Search book summaries using semantic similarity."""

    query_embedding: List[float]  # Pre-computed embedding of user query
    top_k: int = 10  # Maximum number of books to retrieve
    min_similarity: float = 0.2  # Minimum cosine similarity threshold


class SendChatMessageCommand(Command):
    """Forward a user message to the chat backend."""

    payload: BackendChatPayload


class ShowErrorToastCommand(Command):
    """Display a UI toast or snackbar error via effects layer."""

    message: str
    error_code: Optional[str] = None


class PersistChatStateCommand(Command):
    """Persist chat state snapshot for later restoration."""

    snapshot: ChatStateSnapshot


class TrackUsageMetricCommand(Command):
    """Send analytics event related to chat usage."""

    metric: str
    data: Dict[str, Any] = Field(default_factory=dict)


# LLM and Embedding Commands (used by course system and chat)
class EmbedCommand(Command):
    """Generate embedding for text using OpenAI."""

    text: str
    task: Optional[str] = None  # Optional task identifier for context


class GetBookTitlesCommand(Command):
    """Lookup book titles by book IDs (batch lookup)."""

    book_ids: List[str]  # List of book IDs to lookup


class LLMCommand(Command):
    """Call LLM (Claude) for text generation."""

    prompt: Optional[str] = None  # Inline prompt (backward compatible)
    prompt_name: Optional[str] = None  # Prompt name from registry (new way)
    prompt_variables: Dict[str, Any] = Field(default_factory=dict)  # Variables for template substitution
    temperature: float = 0.7
    max_tokens: int = 4000
    task: Optional[str] = None  # Optional task identifier (e.g., 'generate_course_outline')


# Course System Commands
class CreateCourseCommand(Command):
    """Create new course record."""

    course: "Course"  # Will be resolved after import


class CreateSectionsCommand(Command):
    """Create multiple course sections."""

    sections: List["CourseSection"]  # Will be resolved after import


class UpdateCourseCommand(Command):
    """Update course record."""

    course: "Course"  # Will be resolved after import


class UpdateSectionsCommand(Command):
    """Update multiple sections."""

    sections: List["CourseSection"]  # Will be resolved after import


class DeleteSectionsCommand(Command):
    """Delete sections by ID."""

    section_ids: List[str]


class LoadSectionCommand(Command):
    """Load section for delivery."""

    section_id: str


class QuerySectionsCommand(Command):
    """Query sections with filters."""

    course_id: str
    status: Optional[str] = None
    can_standalone: Optional[bool] = None
    max_minutes: Optional[int] = None


class RetrieveChunksCommand(Command):
    """Retrieve specific chunks by ID."""

    chunk_ids: List[str]


class StoreLectureCommand(Command):
    """Store section delivery."""

    delivery: "SectionDelivery"  # Will be resolved after import


class UpdateSectionStatusCommand(Command):
    """Update section status."""

    section_id: str
    status: str  # 'not_started', 'in_progress', 'completed'


class CheckPrerequisitesCommand(Command):
    """Check if prerequisites are met."""

    section_id: str


class RecordCourseHistoryCommand(Command):
    """Record change to course."""

    course_id: str
    change_type: str
    change_description: str
    outline_snapshot: Optional[Dict[str, Any]] = None


class CreateQASessionCommand(Command):
    """Create Q&A session for section."""

    section_id: str
    delivery_id: Optional[str] = None
    lecture_position_seconds: int


class AppendQAMessageCommand(Command):
    """Append message to Q&A session."""

    qa_session_id: str
    messages: List[Dict[str, Any]]  # List of {role, content, timestamp}
    context_chunks: List[str] = Field(default_factory=list)


class EndQASessionCommand(Command):
    """End Q&A session."""

    qa_session_id: str


# Book Summary Generation Commands
class ExtractTOCCommand(Command):
    """Extract table of contents from PDF."""
    pdf_path: Path


class ExtractChapterTextCommand(Command):
    """Extract text for specific chapter."""
    pdf_path: Path
    start_page: int
    end_page: int
    chapter_title: str


class StoreBookSummaryCommand(Command):
    """Store book summary in database."""
    book_id: str
    summary_json: str


class UpdateGenerationProgressCommand(Command):
    """Update generation progress for tracking."""
    section_id: str
    phase: str  # "objectives", "refining", "complete"
    covered_objectives: List[int] = Field(default_factory=list)
    total_objectives: int


class GenerateAudioCommand(Command):
    """Generate audio from lecture script using OpenAI TTS."""
    
    delivery_id: str
    text: str  # Lecture script to convert to speech
    voice: str = "onyx"  # OpenAI TTS voice (onyx for authoritative, clear)
    optional: bool = True  # If True, failures won't block lecture delivery


# Lecture Q&A Commands
class EnhanceQuestionCommand(Command):
    """
    Enhance a question with lecture context for better RAG retrieval.
    
    Takes a potentially vague question and restates it with specific
    context from the lecture for better semantic search.
    """
    question: str
    lecture_context: str  # Full lecture context (course + delivered + remaining)


class GenerateLectureAnswerCommand(Command):
    """
    Generate answer to lecture question maintaining lecture persona.
    
    Uses the same presentation style as the lecture itself,
    incorporating retrieved textbook passages and lecture context.
    """
    enhanced_question: str
    retrieved_chunks: List[Dict[str, Any]]
    lecture_context: str
    presentation_style: str  # e.g., "conversational", "professor", "morning_dj"


class SearchFiguresCommand(Command):
    """Search figure chunks using embedding."""
    embedding: List[float]
    limit: int = 5  # Get top N, will select best 0-3
    similarity_threshold: float = 0.65


class LinkFiguresToDeliveryCommand(Command):
    """Link selected figures to a section delivery."""
    delivery_id: str
    figures: List[Dict[str, Any]]  # Figure metadata with positions


# Late import to avoid circular dependencies
# course_models doesn't import commands, so this is safe
from shared.core.course_models import Course, CourseSection, SectionDelivery

# Rebuild models that use forward references now that models are imported
CreateCourseCommand.model_rebuild()
CreateSectionsCommand.model_rebuild()
UpdateCourseCommand.model_rebuild()
UpdateSectionsCommand.model_rebuild()
StoreLectureCommand.model_rebuild()

