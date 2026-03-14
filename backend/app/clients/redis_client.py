# filepath: backend/app/clients/redis_client.py
"""
Redis client wrapper.

Provides an async Redis client for:
  - **Caching**: GET/SET with TTL, namespaced keys, bulk invalidation
  - **Rate limiting**: Token-bucket / sliding-window helpers
  - **Task broker health**: PING check used by health endpoint

Redis is a *non-critical* dependency — CRUD, chat, and analysis remain
functional if Redis is unavailable.  Document uploads return 503 only
when the Celery broker (Redis) is unreachable at task dispatch time.

Config: ``Settings.redis_url``, ``Settings.redis_password``,
``Settings.redis_ssl``, ``Settings.redis_max_connections``.

Usage::

    from app.clients.redis_client import get_redis_client
    client = get_redis_client()
    await client.set_cached("key", value, ttl=300)
    value = await client.get_cached("key")
"""

from __future__ import annotations

import json
from typing import Any

import redis.asyncio as aioredis

from app.config import Settings, get_settings
from app.observability.logging import get_logger

logger = get_logger(__name__)

# Default TTLs (seconds)
DEFAULT_CACHE_TTL: int = 300  # 5 minutes
LONG_CACHE_TTL: int = 3600  # 1 hour
SHORT_CACHE_TTL: int = 60  # 1 minute


class RedisClient:
    """Async Redis client with caching and rate-limiting helpers."""

    def __init__(self, settings: Settings | None = None) -> None:
        if settings is None:
            settings = get_settings()
        self._settings = settings
        self._pool: aioredis.ConnectionPool | None = None
        self._client: aioredis.Redis | None = None

    # ── Lifecycle ────────────────────────────────────────────────

    async def connect(self) -> None:
        """Initialise the connection pool."""
        if self._client is not None:
            return

        self._pool = aioredis.ConnectionPool.from_url(
            self._settings.redis_url,
            password=self._settings.redis_password,
            max_connections=self._settings.redis_max_connections,
            decode_responses=True,
            socket_connect_timeout=5.0,
            socket_timeout=5.0,
        )
        self._client = aioredis.Redis(connection_pool=self._pool)
        logger.info("Redis client connected", url=self._settings.redis_url)

    async def close(self) -> None:
        """Close the connection pool."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        if self._pool is not None:
            await self._pool.disconnect()
            self._pool = None
            logger.info("Redis client closed")

    @property
    def client(self) -> aioredis.Redis:
        """Return the underlying Redis client. Raises if not connected."""
        if self._client is None:
            raise RuntimeError("Redis client not connected — call connect() first")
        return self._client

    # ── Cache: simple key-value ──────────────────────────────────

    async def set_cached(
        self,
        key: str,
        value: Any,
        *,
        ttl: int = DEFAULT_CACHE_TTL,
        namespace: str = "cache",
    ) -> bool:
        """Store a JSON-serialisable value with TTL.

        Returns True on success, False on failure (non-critical).
        """
        full_key = f"{namespace}:{key}"
        try:
            serialised = json.dumps(value, default=str)
            await self.client.setex(full_key, ttl, serialised)
            return True
        except Exception as exc:
            logger.warning("Redis SET failed", key=full_key, error=str(exc))
            return False

    async def get_cached(
        self,
        key: str,
        *,
        namespace: str = "cache",
    ) -> Any | None:
        """Retrieve a cached value. Returns None on miss or error."""
        full_key = f"{namespace}:{key}"
        try:
            raw = await self.client.get(full_key)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception as exc:
            logger.warning("Redis GET failed", key=full_key, error=str(exc))
            return None

    async def delete_cached(
        self,
        key: str,
        *,
        namespace: str = "cache",
    ) -> bool:
        """Delete a single cached key."""
        full_key = f"{namespace}:{key}"
        try:
            result = await self.client.delete(full_key)
            return bool(result)
        except Exception as exc:
            logger.warning("Redis DELETE failed", key=full_key, error=str(exc))
            return False

    async def invalidate_pattern(
        self,
        pattern: str,
        *,
        namespace: str = "cache",
    ) -> int:
        """Delete all keys matching a glob pattern within a namespace.

        E.g. ``invalidate_pattern("company:*")`` deletes all company cache keys.
        Returns the number of keys deleted.
        """
        full_pattern = f"{namespace}:{pattern}"
        count = 0
        try:
            async for key in self.client.scan_iter(match=full_pattern, count=100):
                await self.client.delete(key)
                count += 1
            return count
        except Exception as exc:
            logger.warning("Redis pattern invalidation failed", pattern=full_pattern, error=str(exc))
            return count

    # ── Cache: hash-based (for structured data) ──────────────────

    async def hset_cached(
        self,
        key: str,
        mapping: dict[str, Any],
        *,
        ttl: int = DEFAULT_CACHE_TTL,
        namespace: str = "cache",
    ) -> bool:
        """Store a dict as a Redis hash with TTL."""
        full_key = f"{namespace}:{key}"
        try:
            serialised = {k: json.dumps(v, default=str) for k, v in mapping.items()}
            await self.client.hset(full_key, mapping=serialised)
            await self.client.expire(full_key, ttl)
            return True
        except Exception as exc:
            logger.warning("Redis HSET failed", key=full_key, error=str(exc))
            return False

    async def hget_cached(
        self,
        key: str,
        field: str,
        *,
        namespace: str = "cache",
    ) -> Any | None:
        """Get a single field from a Redis hash."""
        full_key = f"{namespace}:{key}"
        try:
            raw = await self.client.hget(full_key, field)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception as exc:
            logger.warning("Redis HGET failed", key=full_key, field=field, error=str(exc))
            return None

    async def hgetall_cached(
        self,
        key: str,
        *,
        namespace: str = "cache",
    ) -> dict[str, Any] | None:
        """Get all fields from a Redis hash."""
        full_key = f"{namespace}:{key}"
        try:
            raw = await self.client.hgetall(full_key)
            if not raw:
                return None
            return {k: json.loads(v) for k, v in raw.items()}
        except Exception as exc:
            logger.warning("Redis HGETALL failed", key=full_key, error=str(exc))
            return None

    # ── Rate limiting ────────────────────────────────────────────

    async def check_rate_limit(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
        *,
        namespace: str = "ratelimit",
    ) -> tuple[bool, int]:
        """Sliding-window rate limiter.

        Args:
            key: Unique identifier (e.g. "sec_edgar" or "chat:{session_id}").
            max_requests: Maximum allowed in the window.
            window_seconds: Window size in seconds.

        Returns:
            (allowed, remaining) — ``allowed`` is True if under limit.
        """
        full_key = f"{namespace}:{key}"
        try:
            current = await self.client.incr(full_key)
            if current == 1:
                await self.client.expire(full_key, window_seconds)
            remaining = max(0, max_requests - current)
            return (current <= max_requests, remaining)
        except Exception as exc:
            logger.warning("Redis rate limit check failed", key=full_key, error=str(exc))
            # Fail open — allow the request if Redis is down
            return (True, max_requests)

    # ── Pub/Sub helpers (for future SSE fan-out) ─────────────────

    async def publish(self, channel: str, message: str | dict) -> int:
        """Publish a message to a Redis channel."""
        try:
            payload = json.dumps(message, default=str) if isinstance(message, dict) else message
            result = await self.client.publish(channel, payload)
            return result
        except Exception as exc:
            logger.warning("Redis PUBLISH failed", channel=channel, error=str(exc))
            return 0

    # ── Health ───────────────────────────────────────────────────

    async def health_check(self) -> bool:
        """Return True if Redis is reachable (PING)."""
        try:
            return bool(await self.client.ping())
        except Exception:
            return False

    # ── Low-level access ─────────────────────────────────────────

    async def exists(self, key: str, *, namespace: str = "cache") -> bool:
        """Check if a key exists."""
        full_key = f"{namespace}:{key}"
        try:
            return bool(await self.client.exists(full_key))
        except Exception:
            return False

    async def ttl(self, key: str, *, namespace: str = "cache") -> int:
        """Return remaining TTL in seconds (-1 = no expiry, -2 = missing)."""
        full_key = f"{namespace}:{key}"
        try:
            return await self.client.ttl(full_key)
        except Exception:
            return -2


# =====================================================================
# Module-level singleton
# =====================================================================

_redis_client: RedisClient | None = None


async def init_redis_client(settings: Settings | None = None) -> RedisClient:
    """Initialise and connect the module-level Redis client singleton."""
    global _redis_client
    _redis_client = RedisClient(settings)
    await _redis_client.connect()
    return _redis_client


async def close_redis_client() -> None:
    """Close the module-level Redis client."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None


def get_redis_client() -> RedisClient:
    """Return the module-level Redis client. Must be initialised first."""
    if _redis_client is None:
        raise RuntimeError(
            "Redis client not initialised — call init_redis_client() at startup"
        )
    return _redis_client
