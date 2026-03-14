# filepath: backend/app/api/middleware/error_handler.py
"""
Global error handling for the FastAPI application.

Provides:
- Custom exception classes aligned to the error taxonomy (spec 18.1)
- FastAPI exception handlers that produce a consistent JSON envelope::

      {
          "status": <int>,
          "error": "<category>",
          "message": "<human-readable>",
          "details": [...]  // optional
      }

- A catch-all handler for unhandled ``Exception`` that logs the full
  traceback but returns only a safe generic message to the client
  (no internal details leaked).

Usage:
    Called from ``create_app()`` in ``main.py``::

        from app.api.middleware.error_handler import register_error_handlers
        register_error_handlers(app)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.observability.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = get_logger(__name__)


# =====================================================================
# Custom exception hierarchy
# =====================================================================


class AppError(Exception):
    """Base exception for all application-domain errors.

    Subclasses map 1-to-1 with the error taxonomy categories defined
    in the system specification (18.1).
    """

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code: str = "internal_error"
    message: str = "An unexpected error occurred"

    def __init__(
        self,
        message: str | None = None,
        *,
        details: list[dict[str, Any]] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.message = message or self.__class__.message
        self.details = details
        self.headers = headers
        super().__init__(self.message)


class NotFoundError(AppError):
    """Raised when a requested entity does not exist (404)."""

    status_code = status.HTTP_404_NOT_FOUND
    error_code = "not_found"
    message = "The requested resource was not found"

    def __init__(
        self,
        entity: str = "Resource",
        entity_id: str | Any | None = None,
        **kwargs: Any,
    ) -> None:
        msg = f"{entity} not found"
        if entity_id is not None:
            msg = f"{entity} with id '{entity_id}' not found"
        super().__init__(msg, **kwargs)
        self.entity = entity
        self.entity_id = entity_id


class ConflictError(AppError):
    """Raised on uniqueness / duplicate conflicts (409)."""

    status_code = status.HTTP_409_CONFLICT
    error_code = "conflict"
    message = "The request conflicts with existing data"


class ValidationError(AppError):
    """Raised for business-rule validation failures (422).

    Distinct from Pydantic's ``RequestValidationError`` which is
    handled separately with field-level detail.
    """

    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    error_code = "validation_error"
    message = "Validation failed"


class ExternalServiceError(AppError):
    """Raised when an external dependency is unreachable or errors (502)."""

    status_code = status.HTTP_502_BAD_GATEWAY
    error_code = "external_service_error"
    message = "An external service is currently unavailable"

    def __init__(
        self,
        service: str = "external service",
        message: str | None = None,
        **kwargs: Any,
    ) -> None:
        msg = message or f"Failed to reach {service}"
        super().__init__(msg, **kwargs)
        self.service = service


class RateLimitError(AppError):
    """Raised when the client or an upstream has exceeded rate limits (429)."""

    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    error_code = "rate_limit_exceeded"
    message = "Rate limit exceeded. Please try again later."

    def __init__(
        self,
        retry_after: int | None = None,
        **kwargs: Any,
    ) -> None:
        headers = kwargs.pop("headers", None) or {}
        if retry_after is not None:
            headers["Retry-After"] = str(retry_after)
        super().__init__(headers=headers, **kwargs)
        self.retry_after = retry_after


# =====================================================================
# Response builder
# =====================================================================


def _build_error_response(
    status_code: int,
    error: str,
    message: str,
    details: Sequence[Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Build a consistent JSON error response."""
    body: dict[str, Any] = {
        "status": status_code,
        "error": error,
        "message": message,
    }
    if details:
        body["details"] = jsonable_encoder(details)

    return JSONResponse(
        status_code=status_code,
        content=body,
        headers=headers,
    )


# =====================================================================
# Exception handlers
# =====================================================================


async def _handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    """Handle all ``AppError`` subclasses."""
    logger.warning(
        "Application error",
        error_code=exc.error_code,
        status_code=exc.status_code,
        message=exc.message,
        path=request.url.path,
    )
    return _build_error_response(
        status_code=exc.status_code,
        error=exc.error_code,
        message=exc.message,
        details=exc.details,
        headers=exc.headers,
    )


async def _handle_http_exception(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    """Handle Starlette/FastAPI ``HTTPException`` (auth 401, 403, 404, etc.).

    If the ``detail`` is already a dict (e.g. from ``require_api_key``),
    it is returned as-is inside the envelope.  Otherwise we normalise
    into the standard error shape.
    """
    detail = exc.detail

    # Already structured (e.g. auth middleware sets a dict)
    if isinstance(detail, dict):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": detail},
            headers=getattr(exc, "headers", None),
        )

    # Map status codes to human-friendly error slugs
    error_slug = _STATUS_SLUG_MAP.get(exc.status_code, "error")

    return _build_error_response(
        status_code=exc.status_code,
        error=error_slug,
        message=str(detail) if detail else "An error occurred",
        headers=getattr(exc, "headers", None),
    )


_STATUS_SLUG_MAP: dict[int, str] = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "validation_error",
    429: "rate_limit_exceeded",
    500: "internal_error",
    502: "external_service_error",
    503: "service_unavailable",
}


async def _handle_validation_error(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Handle Pydantic request validation errors with field-level detail."""
    details = []
    for err in exc.errors():
        loc = err.get("loc", ())
        field = ".".join(str(part) for part in loc) if loc else None
        details.append(
            {
                "field": field,
                "reason": err.get("msg", "Invalid value"),
            }
        )

    logger.info(
        "Request validation error",
        path=request.url.path,
        error_count=len(details),
    )

    return _build_error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        error="validation_error",
        message="Request validation failed",
        details=details,
    )


async def _handle_unhandled_exception(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Catch-all for unexpected exceptions.

    Logs the full traceback for debugging but returns only a generic
    message to the client (no internal details leaked).
    """
    logger.exception(
        "Unhandled exception",
        path=request.url.path,
        method=request.method,
        exc_type=type(exc).__name__,
    )
    return _build_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        error="internal_error",
        message="An unexpected internal error occurred",
    )


# =====================================================================
# Registration
# =====================================================================


def register_error_handlers(app: FastAPI) -> None:
    """Register all exception handlers on the FastAPI application.

    Call this from ``create_app()`` **after** middleware is added.
    """
    app.add_exception_handler(AppError, _handle_app_error)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _handle_validation_error)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _handle_unhandled_exception)  # type: ignore[arg-type]
