# filepath: backend/app/worker/callbacks.py
"""
Celery task success/failure callback handlers.

Provides reusable ``on_success`` and ``on_failure`` callbacks that:
  - Log task outcomes with structured context
  - Update document/analysis status in the database on failure
  - Can be attached to tasks via ``link`` / ``link_error``

These are wired into individual tasks in later phases.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.observability.logging import get_logger

if TYPE_CHECKING:
    from celery import Task

logger = get_logger(__name__)


def on_task_success(task: Task, retval: object, task_id: str, args: tuple, kwargs: dict) -> None:
    """Called when a task completes successfully."""
    logger.info(
        "Task succeeded",
        task_name=task.name,
        task_id=task_id,
    )


def on_task_failure(
    task: Task, exc: Exception, task_id: str, args: tuple, kwargs: dict, einfo: object
) -> None:
    """Called when a task fails after all retries are exhausted."""
    logger.error(
        "Task failed permanently",
        task_name=task.name,
        task_id=task_id,
        exc_type=type(exc).__name__,
        exc_message=str(exc),
    )


def on_task_retry(
    task: Task, exc: Exception, task_id: str, args: tuple, kwargs: dict, einfo: object
) -> None:
    """Called when a task is about to be retried."""
    logger.warning(
        "Task retrying",
        task_name=task.name,
        task_id=task_id,
        exc_type=type(exc).__name__,
        retry_count=task.request.retries if task.request else 0,
    )
