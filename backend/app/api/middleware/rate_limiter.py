# filepath: backend/app/api/middleware/rate_limiter.py
"""
Rate-limiting middleware.

Enforces per-IP sliding-window limits:
  - **CRUD** endpoints: ``api_rate_limit_crud`` requests / minute (default 100)
  - **Chat** endpoints:  ``api_rate_limit_chat`` requests / minute (default 20)

Chat endpoints are identified by a ``/chat`` segment in the path.

Uses the Redis-based ``check_rate_limit`` helper from ``RedisClient``.
If Redis is unavailable the middleware **fails open** — requests are allowed
(non-critical dependency, see NFR).

Rate-limit headers on every response:
  - ``X-RateLimit-Limit``
  - ``X-RateLimit-Remaining``
  - ``X-RateLimit-Reset`` (window size in seconds)
  - ``Retry-After`` (only on 429)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response

from app.clients.redis_client import get_redis_client
from app.config import Settings, get_settings
from app.observability.logging import get_logger

logger = get_logger(__name__)

_WINDOW_SECONDS = 60


def _client_ip(request: Request) -> str:
    """Extract client IP from forwarded headers or direct connection."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _is_chat_endpoint(path: str) -> bool:
    """Return True if the path targets a chat endpoint."""
    return "/chat" in path


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate limiter backed by Redis."""

    def __init__(self, app: Request, settings: Settings | None = None) -> None:
        super().__init__(app)
        self._settings = settings or get_settings()

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Only rate-limit API endpoints
        path = request.url.path
        if not path.startswith("/api/v1") or path.endswith("/health"):
            return await call_next(request)

        # OPTIONS (preflight) should not be rate-limited
        if request.method == "OPTIONS":
            return await call_next(request)

        ip = _client_ip(request)
        is_chat = _is_chat_endpoint(path)
        limit = (
            self._settings.api_rate_limit_chat
            if is_chat
            else self._settings.api_rate_limit_crud
        )
        bucket = f"chat:{ip}" if is_chat else f"crud:{ip}"

        # Try Redis rate check
        allowed = True
        remaining = limit
        try:
            redis = get_redis_client()
            allowed, remaining = await redis.check_rate_limit(
                key=bucket,
                max_requests=limit,
                window_seconds=_WINDOW_SECONDS,
            )
        except RuntimeError:
            # Redis not initialised — fail open
            logger.debug("rate_limiter_redis_unavailable", ip=ip, path=path)
        except Exception as exc:
            logger.warning("rate_limiter_error", error=str(exc), ip=ip)

        if not allowed:
            logger.info(
                "rate_limited",
                ip=ip,
                path=path,
                bucket=bucket,
                limit=limit,
            )
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded. Please try again later.",
                },
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(_WINDOW_SECONDS),
                    "Retry-After": str(_WINDOW_SECONDS),
                },
            )

        response = await call_next(request)

        # Attach rate-limit info headers
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(_WINDOW_SECONDS)

        return response
