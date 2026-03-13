"""
Request ID middleware.

Generates or propagates a unique request_id (UUID) on every request:
- Reads from incoming X-Request-ID header if present (propagation)
- Generates a new UUID v4 if not present
- Injects into structlog context (all log entries carry request_id)
- Sets X-Request-ID response header for client correlation

NFR-500: All operations MUST carry a request_id for distributed tracing.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

_REQUEST_ID_HEADER = "X-Request-ID"


class RequestIDMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that manages request_id lifecycle per request."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Extract or generate request_id
        request_id = request.headers.get(_REQUEST_ID_HEADER) or str(uuid.uuid4())

        # Store on request state for access in route handlers
        request.state.request_id = request_id

        # Bind to structlog context so all log entries include request_id
        ctx_token: Any = structlog.contextvars.bind_contextvars(request_id=request_id)

        try:
            response = await call_next(request)
        finally:
            # Clear structlog context vars for this request
            structlog.contextvars.unbind_contextvars("request_id")

        # Set response header
        response.headers[_REQUEST_ID_HEADER] = request_id

        return response
