"""
Structured logging setup using structlog.

Configures structlog with:
- JSON output for production, pretty console output for development
- Standard fields: timestamp, level, message, service, logger
- Sensitive data redaction (API keys, passwords, connection strings)
- OpenTelemetry integration for trace/span context injection
- Context variable support for request_id, company_id, document_id

NFR-501: Structured logging (JSON) exported via OpenTelemetry to Application Insights
NFR-503: No sensitive data in logs
"""

from __future__ import annotations

import logging
import re
import sys
from typing import Any

import structlog

from app.config import AppEnvironment, Settings

# ── Sensitive data patterns for redaction ────────────────────────

_SENSITIVE_KEYS = frozenset(
    {
        "api_key",
        "api-key",
        "apikey",
        "password",
        "secret",
        "token",
        "authorization",
        "connection_string",
        "connection-string",
        "connectionstring",
        "azure_openai_api_key",
        "openai_api_key",
        "db_password",
        "redis_password",
        "azure_storage_connection_string",
        "applicationinsights_connection_string",
    }
)

_SENSITIVE_VALUE_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9]{20,}", re.ASCII),  # OpenAI API keys
    re.compile(r"DefaultEndpointsProtocol=https;AccountName=.*", re.ASCII),  # Azure conn strings
    re.compile(r"postgresql(\+asyncpg)?://[^@]+@", re.ASCII),  # DB URLs with creds
    re.compile(r"redis://:[^@]+@", re.ASCII),  # Redis URLs with password
]

_REDACTED = "***REDACTED***"


def _redact_sensitive_data(
    logger: Any,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Structlog processor that redacts sensitive values from log entries."""
    for key, value in list(event_dict.items()):
        if not isinstance(value, str):
            continue
        # Check key names
        if key.lower() in _SENSITIVE_KEYS:
            event_dict[key] = _REDACTED
            continue
        # Check value patterns
        for pattern in _SENSITIVE_VALUE_PATTERNS:
            if pattern.search(value):
                event_dict[key] = _REDACTED
                break
    return event_dict


# ── OpenTelemetry context injection ──────────────────────────────


def _add_otel_context(
    logger: Any,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Inject OpenTelemetry trace and span IDs into log entries if available."""
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        ctx = span.get_span_context()
        if ctx and ctx.trace_id != 0:
            event_dict["trace_id"] = format(ctx.trace_id, "032x")
            event_dict["span_id"] = format(ctx.span_id, "016x")
    except ImportError:
        pass
    return event_dict


# ── Service context injection ────────────────────────────────────


def _make_service_processor(service_name: str):
    """Create a processor that adds the service name to every log entry."""

    def _add_service(
        logger: Any,
        method_name: str,
        event_dict: dict[str, Any],
    ) -> dict[str, Any]:
        event_dict.setdefault("service", service_name)
        return event_dict

    return _add_service


# ── Setup ────────────────────────────────────────────────────────


def setup_logging(settings: Settings) -> None:
    """
    Configure structlog and stdlib logging for the application.

    Args:
        settings: Application settings for environment and log level.
    """
    is_dev = settings.app_env == AppEnvironment.DEVELOPMENT
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # ── Shared processors (used by both structlog and stdlib) ────
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        _make_service_processor(settings.otel_service_name),
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
        _add_otel_context,
        _redact_sensitive_data,
    ]

    if is_dev:
        # Development: pretty console output
        renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer(
            colors=True
        )
    else:
        # Production/staging: JSON output for Application Insights
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # ── Configure stdlib logging to use structlog formatting ─────
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    # ── Quiet noisy third-party loggers ──────────────────────────
    for noisy_logger in (
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",
        "sqlalchemy.engine",
        "httpx",
        "httpcore",
        "celery",
        "azure",
    ):
        logging.getLogger(noisy_logger).setLevel(
            logging.WARNING if not is_dev else logging.INFO
        )

    # ── Log startup confirmation ─────────────────────────────────
    log = structlog.get_logger("app.observability.logging")
    log.info(
        "Logging configured",
        environment=settings.app_env.value,
        log_level=settings.log_level,
        renderer="console" if is_dev else "json",
    )


def get_logger(name: str = __name__) -> structlog.stdlib.BoundLogger:
    """
    Get a structlog logger bound to the given name.

    Usage:
        from app.observability.logging import get_logger
        logger = get_logger(__name__)
        logger.info("Something happened", company_id=uuid)
    """
    return structlog.get_logger(name)
