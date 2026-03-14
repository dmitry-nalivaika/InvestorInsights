# filepath: backend/app/worker/celery_app.py
"""
Celery application configuration.

Creates the Celery app instance with:
  - Redis broker and result backend (from Settings)
  - Three task queues: ``ingestion``, ``analysis``, ``sec_fetch``
  - Retry, serialisation, and time-limit settings
  - Task auto-discovery from ``app.worker.tasks``

Worker launch command::

    celery -A app.worker.celery_app worker \
        --loglevel=info --concurrency=4 \
        --queues=ingestion,analysis,sec_fetch \
        --max-tasks-per-child=50
"""

from __future__ import annotations

from celery import Celery
from kombu import Exchange, Queue

from app.config import get_settings

# ── Load settings ────────────────────────────────────────────────
_settings = get_settings()

# ── Create Celery app ────────────────────────────────────────────
celery_app = Celery("investorinsights")

celery_app.config_from_object(
    {
        # ── Broker / backend ─────────────────────────────────────
        "broker_url": _settings.celery_broker_url,
        "result_backend": _settings.celery_result_backend,
        "broker_connection_retry_on_startup": True,
        # ── Serialisation ────────────────────────────────────────
        "accept_content": ["json"],
        "task_serializer": "json",
        "result_serializer": "json",
        "result_expires": 3600,  # 1 hour
        # ── Time limits ──────────────────────────────────────────
        "task_time_limit": _settings.celery_task_time_limit,
        "task_soft_time_limit": _settings.celery_task_soft_time_limit,
        # ── Reliability ──────────────────────────────────────────
        "task_acks_late": True,
        "worker_prefetch_multiplier": 1,
        "worker_max_tasks_per_child": 50,
        "worker_concurrency": _settings.worker_concurrency,
        # ── Queues ───────────────────────────────────────────────
        "task_default_queue": "ingestion",
        "task_default_exchange": "tasks",
        "task_default_routing_key": "ingestion",
        "task_queues": (
            Queue("ingestion", Exchange("tasks"), routing_key="ingestion"),
            Queue("analysis", Exchange("tasks"), routing_key="analysis"),
            Queue("sec_fetch", Exchange("tasks"), routing_key="sec_fetch"),
        ),
        # ── Task routing ─────────────────────────────────────────
        "task_routes": {
            "app.worker.tasks.ingestion_tasks.*": {"queue": "ingestion"},
            "app.worker.tasks.analysis_tasks.*": {"queue": "analysis"},
            "app.worker.tasks.sec_fetch_tasks.*": {"queue": "sec_fetch"},
        },
        # ── Auto-discovery ───────────────────────────────────────
        "include": [
            "app.worker.tasks.ingestion_tasks",
            "app.worker.tasks.analysis_tasks",
            "app.worker.tasks.sec_fetch_tasks",
        ],
    }
)
