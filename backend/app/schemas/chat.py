# filepath: backend/app/schemas/chat.py
"""Pydantic schemas for Chat / RAG endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import Field

from app.schemas.common import AppBaseModel, PaginatedResponse

if TYPE_CHECKING:
    import uuid
    from datetime import datetime

# ── Request schemas ──────────────────────────────────────────────


class RetrievalConfig(AppBaseModel):
    """Optional RAG retrieval tuning parameters."""

    top_k: int = Field(15, ge=1, le=50)
    score_threshold: float = Field(0.65, ge=0.0, le=1.0)
    query_expansion: bool = True
    filter_doc_types: list[str] | None = None
    filter_year_min: int | None = None
    filter_year_max: int | None = None
    filter_sections: list[str] | None = None


class ChatRequest(AppBaseModel):
    """POST /api/v1/companies/{company_id}/chat."""

    message: str = Field(..., min_length=1, max_length=10000)
    session_id: uuid.UUID | None = None
    retrieval_config: RetrievalConfig | None = None


# ── Response schemas (non-SSE) ───────────────────────────────────


class ChatMessageRead(AppBaseModel):
    """A single message within a chat session."""

    id: uuid.UUID
    role: str
    content: str
    sources: dict[str, Any] | None = None
    token_count: int | None = None
    model_used: str | None = None
    created_at: datetime


class ChatSessionRead(AppBaseModel):
    """Chat session summary for list endpoints."""

    id: uuid.UUID
    company_id: uuid.UUID
    title: str | None = None
    message_count: int = 0
    created_at: datetime
    updated_at: datetime


class ChatSessionDetail(ChatSessionRead):
    """GET /api/v1/companies/{company_id}/chat/sessions/{session_id}."""

    messages: list[ChatMessageRead] = Field(default_factory=list)


class ChatSessionList(PaginatedResponse[ChatSessionRead]):
    """Paginated list of chat sessions."""

    pass


# ── SSE event payloads ───────────────────────────────────────────


class SSESessionEvent(AppBaseModel):
    """SSE 'session' event — sent at start of a new chat turn."""

    session_id: uuid.UUID
    title: str | None = None


class SSESourcesEvent(AppBaseModel):
    """SSE 'sources' event — retrieved context chunks."""

    sources: list[dict[str, Any]]


class SSETokenEvent(AppBaseModel):
    """SSE 'token' event — single streamed token."""

    token: str


class SSEDoneEvent(AppBaseModel):
    """SSE 'done' event — signals end of generation."""

    message_id: uuid.UUID
    token_count: int


class SSEErrorEvent(AppBaseModel):
    """SSE 'error' event — sent if generation fails mid-stream."""

    error: str
    message: str
