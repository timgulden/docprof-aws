from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class IngestionRun(BaseModel):
    """Immutable snapshot describing a single ingestion execution."""

    model_config = ConfigDict(frozen=False)

    run_id: str = Field(default_factory=lambda: str(uuid4()))
    book_title: Optional[str] = None
    book_id: Optional[str] = None
    pdf_path: Optional[str] = None
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    total_chunks: int = 0
    total_figures: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class IngestionState(BaseModel):
    """Top-level immutable state for ingestion operations."""

    model_config = ConfigDict(frozen=False)

    current_run: Optional[IngestionRun] = None
    history: List[IngestionRun] = Field(default_factory=list)


class LogicResult(BaseModel):
    """Functional output from logic layer: new state + commands."""

    model_config = ConfigDict(frozen=False)

    new_state: BaseModel
    commands: List["Command"] = Field(default_factory=list)
    ui_message: Optional[str] = None


# Late import to avoid circular dependency at type-check time.
from shared.core.commands import Command  # noqa: E402  pylint: disable=wrong-import-position

