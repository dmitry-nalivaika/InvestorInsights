# filepath: backend/app/schemas/chat.py
"""Pydantic schemas for Chat / RAG endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import Field

from app.schemas.common import AppBaseModel, PaginatedResponse


# ── Request schemas ──────────────────────────────────────────────


class RetrievalConfig(AppBaseModel):
    """Optional RAG retrieval tuning parameters."""

    top_k: int = Field(15, ge=1, le=50)
    score_threshold: float = Field(0.65, ge=0.0, le=1.0)
    query_expansion: bool = True
    filter_doc_types: Optional[List[str]] = None
    filter_year_min: Optional[int] = None
    filter_year_max: Optional[int] = None
    filter_sections: Optional[List[str]] = None


class ChatRequest(AppBaseModel):
    """POST /api/v1/companies/{company_id}/chat."""

    message: str = Field(..., min_length=1, max_length=10000)
    session_id: Optional[uuid.UUID] = None
    retrieval_config: Optional[RetrievalConfig] = None


# ── Response schemas (non-SSE) ───────────────────────────────────


class ChatMessageRead(AppBaseModel):
    """A single message within a chat session."""

    id: uuid.UUID
    role: str
    content: str
    sources: Optional[Dict[str, Any]] = None
    token_count: Optional[int] = None
    model_used: Optional[str] = None
    created_at: datetime


class ChatSessionRead(AppBaseModel):
    """Chat session summary for list endpoints."""

    id: uuid.UUID
    company_id: uuid.UUID
    title: Optional[str] = None
    message_count: int = 0
    created_at: datetime
    updated_at: datetime


class ChatSessionDetail(ChatSessionRead):
    """GET /api/v1/companies/{company_id}/chat/sessions/{session_id}."""

    messages: List[ChatMessageRead] = Field(default_factory=list)


class ChatSessionList(PaginatedResponse[ChatSessionRead]):
    """Paginated list of chat sessions."""

    pass


# ── SSE event payloads ───────────────────────────────────────────


class SSESessionEvent(AppBaseModel):
    """SSE 'session' event — sent at start of a new chat turn."""

    session_id: uuid.UUID
    title: Optional[str] = None


class SSESourcesEvent(AppBaseModel):
    """SSE 'sources' event — retrieved context chunks."""

    sources: List[Dict[str, Any]]


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
