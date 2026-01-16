from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Sequence, Union
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


ChatStatus = Literal["idle", "awaiting_response", "restoring"]


class FigureAttachment(BaseModel):
    """Lightweight metadata for figures referenced in chat messages."""

    model_config = ConfigDict(frozen=True)

    figure_id: str
    image_url: str
    caption: str
    source: Optional[str] = None


class ChatError(BaseModel):
    """Structured error passed through chat state."""

    model_config = ConfigDict(frozen=True)

    message: str
    code: Optional[str] = None
    retryable: bool = False
    details: Dict[str, Any] = Field(default_factory=dict)


class ChatMessage(BaseModel):
    """Immutable chat message as rendered in the UI."""

    model_config = ConfigDict(frozen=False)

    id: str = Field(default_factory=lambda: str(uuid4()))
    role: Literal["user", "assistant"]
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    figures: List[FigureAttachment] = Field(default_factory=list)
    audio_url: Optional[str] = None
    sources: List[SourceCitation] = Field(default_factory=list)
    citation_spans: List[CitationSpan] = Field(default_factory=list)  # Spans of cited text
    general_spans: List[GeneralKnowledgeSpan] = Field(default_factory=list)  # Spans of general knowledge


class ChatState(BaseModel):
    """Top-level chat state snapshot."""

    model_config = ConfigDict(frozen=False)

    session_id: Optional[str] = None
    session_name: Optional[str] = None  # User-friendly title
    session_type: Literal["chat", "lecture", "quiz", "case_study"] = "chat"
    session_context: Optional[str] = None  # Hidden guiding context (tone, format, trajectory)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    messages: List[ChatMessage] = Field(default_factory=list)
    status: ChatStatus = "idle"
    error: Optional[ChatError] = None
    ui_message: Optional[str] = None


class ChatStateSnapshot(BaseModel):
    """Serializable snapshot of chat state used for persistence."""

    model_config = ConfigDict(frozen=True)

    session_id: Optional[str]
    session_name: Optional[str]
    session_type: Literal["chat", "lecture", "quiz", "case_study"]
    session_context: Optional[str]
    created_at: datetime
    updated_at: datetime
    messages: List[ChatMessage]

    @classmethod
    def from_state(cls, state: ChatState) -> "ChatStateSnapshot":
        return cls(
            session_id=state.session_id,
            session_name=state.session_name,
            session_type=state.session_type,
            session_context=state.session_context,
            created_at=state.created_at,
            updated_at=state.updated_at,
            messages=[message.model_copy(deep=True) for message in state.messages],
        )


class BackendChatPayload(BaseModel):
    """Payload sent to backend when user submits a new message."""

    model_config = ConfigDict(frozen=True)

    message: str
    with_audio: bool = False
    session_id: Optional[str] = None


class SourceCitation(BaseModel):
    """Source citation for a chunk referenced in an assistant message."""

    model_config = ConfigDict(frozen=True)

    citation_id: str  # e.g., "[1]", "[2]"
    chunk_id: str
    chunk_type: Literal["chapter", "2page", "figure"]
    book_id: str
    book_title: str
    chapter_number: Optional[int] = None
    chapter_title: Optional[str] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    target_page: Optional[int] = None  # Page to jump to in PDF viewer (center page for 2-page chunks)
    content: str  # The actual text used
    score: Optional[float] = None  # Similarity score


class CitationSpan(BaseModel):
    """A span of text that is cited from sources."""

    model_config = ConfigDict(frozen=True)

    start: int  # Character position start
    end: int  # Character position end
    citation_ids: List[str]  # List of citation IDs like ["1", "2"]


class GeneralKnowledgeSpan(BaseModel):
    """A span of text that is general knowledge, not directly from sources."""

    model_config = ConfigDict(frozen=True)

    start: int  # Character position start
    end: int  # Character position end


class AssistantMessagePayload(BaseModel):
    """Assistant response payload returned by the backend effects layer."""

    model_config = ConfigDict(frozen=True)

    message_id: Optional[str] = Field(default_factory=lambda: str(uuid4()))
    content: str
    figures: List[FigureAttachment] = Field(default_factory=list)
    audio_url: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    sources: List[SourceCitation] = Field(default_factory=list)
    citation_spans: List[CitationSpan] = Field(default_factory=list)  # Spans of cited text
    general_spans: List[GeneralKnowledgeSpan] = Field(default_factory=list)  # Spans of general knowledge


class ChatEvent(BaseModel):
    """Base class for UI → logic events in the chat flow."""

    model_config = ConfigDict(frozen=True)

    event_type: str


class UserSubmittedMessage(ChatEvent):
    event_type: Literal["user_submitted_message"] = "user_submitted_message"
    text: str
    with_audio: bool = False


class BackendMessageReceived(ChatEvent):
    event_type: Literal["backend_message_received"] = "backend_message_received"
    session_id: Optional[str] = None
    messages: Sequence[AssistantMessagePayload] = Field(default_factory=list)
    ui_message: Optional[str] = None


class BackendFailed(ChatEvent):
    event_type: Literal["backend_failed"] = "backend_failed"
    session_id: Optional[str] = None
    error: ChatError


class SessionRestored(ChatEvent):
    event_type: Literal["session_restored"] = "session_restored"
    snapshot: ChatStateSnapshot


class ResetRequested(ChatEvent):
    event_type: Literal["reset_requested"] = "reset_requested"


ChatEventType = Union[
    UserSubmittedMessage,
    BackendMessageReceived,
    BackendFailed,
    SessionRestored,
    ResetRequested,
]


