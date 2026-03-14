# filepath: backend/app/observability/metrics.py
"""
Custom OpenTelemetry metric instrumentation.

Defines all application-level metrics emitted via OpenTelemetry SDK and
exported to Azure Application Insights.

Metrics (from plan.md — Observability § Metrics):

**Counters**:
  - ``ingestion_documents_total`` — documents ingested
  - ``chat_messages_total`` — chat messages processed
  - ``analysis_runs_total`` — analysis runs completed
  - ``llm_api_calls_total`` — LLM API calls made
  - ``llm_tokens_total`` — LLM tokens consumed (labels: type=prompt|completion, model)

**Histograms**:
  - ``ingestion_duration_seconds`` — time to ingest a document
  - ``chat_retrieval_duration_seconds`` — time for RAG retrieval step
  - ``chat_llm_duration_seconds`` — time for LLM completion in chat
  - ``analysis_duration_seconds`` — time to run an analysis profile

**Gauges** (implemented as UpDownCounters for OTel compatibility):
  - ``companies_total`` — current number of tracked companies
  - ``documents_total`` — current number of documents
  - ``vectors_total`` — current number of vector embeddings
  - ``celery_workers_active`` — current active Celery workers

Usage::

    from app.observability.metrics import get_metrics
    m = get_metrics()
    m.ingestion_documents_total.add(1, {"doc_type": "10-K"})
    m.llm_tokens_total.add(150, {"type": "prompt", "model": "gpt-4o-mini"})
    with m.measure_duration(m.chat_llm_duration_seconds):
        response = await llm_client.chat(...)
"""

from __future__ import annotations

import contextlib
import time
from typing import TYPE_CHECKING, Any

from opentelemetry import metrics

from app.observability.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Iterator

    from opentelemetry.metrics import (
        Counter,
        Histogram,
        Meter,
        UpDownCounter,
    )

logger = get_logger(__name__)

# =====================================================================
# Histogram bucket boundaries (seconds)
# =====================================================================

# Ingestion can take minutes for large filings
_INGESTION_BUCKETS = (1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0)

# RAG retrieval is typically sub-second
_RETRIEVAL_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

# LLM calls: a few seconds to two minutes
_LLM_BUCKETS = (0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0)

# Analysis runs: seconds to minutes
_ANALYSIS_BUCKETS = (1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0)


# =====================================================================
# Metrics container
# =====================================================================


class AppMetrics:
    """Holds all application-level OpenTelemetry metric instruments.

    Created once at startup via :func:`init_metrics`.  Retrieve the
    singleton via :func:`get_metrics`.
    """

    def __init__(self, meter: Meter) -> None:
        self._meter = meter

        # ── Counters ─────────────────────────────────────────────
        self.ingestion_documents_total: Counter = meter.create_counter(
            name="ingestion_documents_total",
            description="Total number of documents ingested",
            unit="1",
        )

        self.chat_messages_total: Counter = meter.create_counter(
            name="chat_messages_total",
            description="Total number of chat messages processed",
            unit="1",
        )

        self.analysis_runs_total: Counter = meter.create_counter(
            name="analysis_runs_total",
            description="Total number of analysis runs completed",
            unit="1",
        )

        self.llm_api_calls_total: Counter = meter.create_counter(
            name="llm_api_calls_total",
            description="Total number of LLM API calls made",
            unit="1",
        )

        self.llm_tokens_total: Counter = meter.create_counter(
            name="llm_tokens_total",
            description="Total LLM tokens consumed (labels: type=prompt|completion, model)",
            unit="1",
        )

        # ── Histograms ──────────────────────────────────────────
        self.ingestion_duration_seconds: Histogram = meter.create_histogram(
            name="ingestion_duration_seconds",
            description="Duration of document ingestion pipeline",
            unit="s",
        )

        self.chat_retrieval_duration_seconds: Histogram = meter.create_histogram(
            name="chat_retrieval_duration_seconds",
            description="Duration of RAG retrieval step",
            unit="s",
        )

        self.chat_llm_duration_seconds: Histogram = meter.create_histogram(
            name="chat_llm_duration_seconds",
            description="Duration of LLM completion in chat",
            unit="s",
        )

        self.analysis_duration_seconds: Histogram = meter.create_histogram(
            name="analysis_duration_seconds",
            description="Duration of analysis profile execution",
            unit="s",
        )

        # ── Gauges (UpDownCounter for OTel SDK compatibility) ────
        # OTel Python SDK does not have a synchronous Gauge;
        # UpDownCounter allows increment/decrement to track current values.
        self.companies_total: UpDownCounter = meter.create_up_down_counter(
            name="companies_total",
            description="Current number of tracked companies",
            unit="1",
        )

        self.documents_total: UpDownCounter = meter.create_up_down_counter(
            name="documents_total",
            description="Current number of documents",
            unit="1",
        )

        self.vectors_total: UpDownCounter = meter.create_up_down_counter(
            name="vectors_total",
            description="Current number of vector embeddings",
            unit="1",
        )

        self.celery_workers_active: UpDownCounter = meter.create_up_down_counter(
            name="celery_workers_active",
            description="Current number of active Celery workers",
            unit="1",
        )

        logger.info("Application metrics initialised")

    # ── Duration measurement helper ──────────────────────────────

    @contextlib.contextmanager
    def measure_duration(
        self,
        histogram: Histogram,
        attributes: dict[str, Any] | None = None,
    ) -> Iterator[None]:
        """Context manager that records elapsed time to a histogram.

        Usage::

            with metrics.measure_duration(metrics.chat_llm_duration_seconds):
                result = await client.chat(...)

        Args:
            histogram: The histogram instrument to record to.
            attributes: Optional OTel attributes (labels) for the measurement.
        """
        start = time.monotonic()
        try:
            yield
        finally:
            elapsed = time.monotonic() - start
            histogram.record(elapsed, attributes=attributes or {})

    # ── Convenience helpers for LLM token tracking ───────────────

    def record_llm_tokens(
        self,
        *,
        prompt_tokens: int,
        completion_tokens: int,
        model: str,
    ) -> None:
        """Record prompt and completion token counts for an LLM call.

        Args:
            prompt_tokens: Number of prompt/input tokens.
            completion_tokens: Number of completion/output tokens.
            model: Model name (e.g. ``gpt-4o-mini``).
        """
        if prompt_tokens > 0:
            self.llm_tokens_total.add(
                prompt_tokens, {"type": "prompt", "model": model}
            )
        if completion_tokens > 0:
            self.llm_tokens_total.add(
                completion_tokens, {"type": "completion", "model": model}
            )

    def record_llm_call(self, *, model: str, operation: str = "chat") -> None:
        """Increment the LLM API call counter.

        Args:
            model: Model name.
            operation: Operation type (``chat``, ``embedding``, etc.).
        """
        self.llm_api_calls_total.add(1, {"model": model, "operation": operation})


# =====================================================================
# Module-level singleton
# =====================================================================

_metrics: AppMetrics | None = None


def init_metrics(service_name: str = "investorinsights-api") -> AppMetrics:
    """Create and register application metrics with the OTel MeterProvider.

    Should be called once at application startup (e.g. in the FastAPI
    lifespan).  Subsequent calls return the existing instance.

    Args:
        service_name: The OTel service name used as the meter scope.

    Returns:
        The singleton :class:`AppMetrics` instance.
    """
    global _metrics
    if _metrics is not None:
        return _metrics

    meter = metrics.get_meter(service_name)
    _metrics = AppMetrics(meter)
    logger.info("Metrics singleton initialised", service_name=service_name)
    return _metrics


def get_metrics() -> AppMetrics:
    """Return the module-level metrics singleton.

    Raises:
        RuntimeError: If :func:`init_metrics` has not been called.
    """
    if _metrics is None:
        raise RuntimeError(
            "Metrics not initialised — call init_metrics() at startup"
        )
    return _metrics


def get_metrics_optional() -> AppMetrics | None:
    """Return the metrics singleton, or ``None`` if not yet initialised.

    Useful in code paths that may execute before startup completes
    (e.g. Celery tasks starting before the API lifespan).
    """
    return _metrics
