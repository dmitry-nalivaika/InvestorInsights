# filepath: backend/app/api/tasks.py
"""Async task status API.

Endpoints:
  GET /api/v1/tasks/{task_id} — Get status of an async background task
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.api.middleware.error_handler import NotFoundError
from app.observability.logging import get_logger
from app.schemas.common import TaskStatusResponse

logger = get_logger(__name__)

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get(
    "/{task_id}",
    response_model=TaskStatusResponse,
    summary="Get async task status",
    description="Check the status of a background task (ingestion, SEC fetch, etc.).",
)
async def get_task_status(task_id: uuid.UUID) -> TaskStatusResponse:
    """Query Celery for the status of a background task."""
    from app.worker.celery_app import celery_app

    result = celery_app.AsyncResult(str(task_id))

    # Map Celery states to our API states
    state_map = {
        "PENDING": "pending",
        "STARTED": "running",
        "SUCCESS": "completed",
        "FAILURE": "failed",
        "RETRY": "running",
        "REVOKED": "failed",
    }

    task_status = state_map.get(result.state, "pending")

    task_result = None
    error = None

    if result.state == "SUCCESS" and result.result:
        task_result = result.result if isinstance(result.result, dict) else {"result": str(result.result)}
    elif result.state == "FAILURE":
        error = str(result.result) if result.result else "Task failed"

    return TaskStatusResponse(
        task_id=task_id,
        status=task_status,
        result=task_result,
        error=error,
    )
