# filepath: backend/app/schemas/common.py
"""Shared Pydantic schemas used across multiple domains."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class AppBaseModel(BaseModel):
    """Project-wide base model with shared config."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=True,
    )


# ── Pagination ───────────────────────────────────────────────────


class PaginationParams(AppBaseModel):
    """Query parameters for paginated list endpoints."""

    limit: int = Field(50, ge=1, le=100, description="Items per page")
    offset: int = Field(0, ge=0, description="Number of items to skip")


class PaginatedResponse(AppBaseModel, Generic[T]):
    """Envelope for paginated list responses."""

    items: List[T]
    total: int = Field(..., ge=0)
    limit: int
    offset: int


# ── Errors ───────────────────────────────────────────────────────


class ErrorDetail(AppBaseModel):
    """Optional structured detail attached to an error response."""

    field: Optional[str] = None
    reason: Optional[str] = None


class ErrorResponse(AppBaseModel):
    """Standard error envelope returned by all error handlers."""

    status: int
    error: str
    message: str
    details: Optional[List[ErrorDetail]] = None


# ── Sorting ──────────────────────────────────────────────────────


class SortOrder(str):
    """Sort direction — kept as plain str for query param binding."""

    ASC = "asc"
    DESC = "desc"


# ── Task status ──────────────────────────────────────────────────


class TaskProgress(AppBaseModel):
    """Progress info for async background tasks."""

    current: int = 0
    total: int = 0
    message: str = ""


class TaskStatusResponse(AppBaseModel):
    """Response for GET /api/v1/tasks/{task_id}."""

    task_id: uuid.UUID
    status: str = Field(..., description="pending | running | completed | failed")
    progress: Optional[TaskProgress] = None
    result: Optional[dict] = None
    error: Optional[str] = None


# ── Health ───────────────────────────────────────────────────────


class HealthComponent(AppBaseModel):
    """Individual health-check probe result."""

    status: str = Field(..., description="healthy | unhealthy")
    latency_ms: Optional[float] = None
    error: Optional[str] = None


class HealthResponse(AppBaseModel):
    """Response for GET /api/v1/health."""

    status: str = Field(..., description="healthy | degraded | unhealthy")
    components: dict[str, HealthComponent] = Field(default_factory=dict)
    version: str
    uptime_seconds: int
