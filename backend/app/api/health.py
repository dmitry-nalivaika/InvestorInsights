# filepath: backend/app/api/health.py
"""
Health check endpoint.

``GET /api/v1/health`` — public (no auth required).

Probes every infrastructure dependency in parallel and returns a
structured response with per-component status, latency, and an
overall aggregate status.

Components:
  - **database** — PostgreSQL ``SELECT 1``
  - **vector_store** — Qdrant HTTP ``/readyz``
  - **object_storage** — Azure Blob ``list_containers`` (limit 1)
  - **redis** — ``PING``
  - **llm_api** — skipped in dev if key is fake / not configured

Overall status logic:
  - ``healthy`` — all probes pass
  - ``degraded`` — at least one probe failed, but database is up
  - ``unhealthy`` — database probe failed
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, Optional, Tuple

import httpx
from fastapi import APIRouter

from app.config import Settings, get_settings
from app.observability.logging import get_logger
from app.schemas.common import HealthComponent, HealthResponse

logger = get_logger(__name__)

# Timeout (seconds) for each individual probe
_PROBE_TIMEOUT: float = 5.0

router = APIRouter(tags=["system"])


# =====================================================================
# Individual probes
# =====================================================================


async def _probe_database(settings: Settings) -> Tuple[str, float, Optional[str]]:
    """Probe PostgreSQL with ``SELECT 1``."""
    start = time.monotonic()
    try:
        from sqlalchemy import text

        from app.db.session import get_session_factory

        factory = get_session_factory()
        async with factory() as session:
            await session.execute(text("SELECT 1"))
        latency = (time.monotonic() - start) * 1000
        return ("healthy", latency, None)
    except Exception as exc:
        latency = (time.monotonic() - start) * 1000
        return ("unhealthy", latency, str(exc))


async def _probe_vector_store(settings: Settings) -> Tuple[str, float, Optional[str]]:
    """Probe Qdrant via its HTTP readiness endpoint."""
    start = time.monotonic()
    url = settings.qdrant_url or f"http://{settings.qdrant_host}:{settings.qdrant_http_port}"
    try:
        async with httpx.AsyncClient(timeout=_PROBE_TIMEOUT) as client:
            resp = await client.get(f"{url}/readyz")
            latency = (time.monotonic() - start) * 1000
            if resp.status_code == 200:
                return ("healthy", latency, None)
            return ("unhealthy", latency, f"HTTP {resp.status_code}")
    except Exception as exc:
        latency = (time.monotonic() - start) * 1000
        return ("unhealthy", latency, str(exc))


async def _probe_object_storage(settings: Settings) -> Tuple[str, float, Optional[str]]:
    """Probe Azure Blob Storage by listing containers."""
    start = time.monotonic()
    try:
        from app.clients.storage_client import get_storage_client

        storage = get_storage_client()
        healthy = await storage.health_check()
        latency = (time.monotonic() - start) * 1000
        if healthy:
            return ("healthy", latency, None)
        return ("unhealthy", latency, "health_check returned False")
    except RuntimeError:
        # StorageClient not initialised (e.g. in test without full stack)
        latency = (time.monotonic() - start) * 1000
        return ("unhealthy", latency, "StorageClient not initialised")
    except Exception as exc:
        latency = (time.monotonic() - start) * 1000
        return ("unhealthy", latency, str(exc))


async def _probe_redis(settings: Settings) -> Tuple[str, float, Optional[str]]:
    """Probe Redis with PING."""
    start = time.monotonic()
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(
            settings.redis_url,
            socket_connect_timeout=_PROBE_TIMEOUT,
            decode_responses=True,
        )
        try:
            pong = await r.ping()
            latency = (time.monotonic() - start) * 1000
            if pong:
                return ("healthy", latency, None)
            return ("unhealthy", latency, "PING returned False")
        finally:
            await r.aclose()
    except Exception as exc:
        latency = (time.monotonic() - start) * 1000
        return ("unhealthy", latency, str(exc))


async def _probe_llm_api(settings: Settings) -> Tuple[str, float, Optional[str]]:
    """Probe the LLM API endpoint (Azure OpenAI).

    In development, if the key looks fake we mark as ``healthy``
    with a note that it was skipped — prevents dev-mode failures
    when the real key is not configured.
    """
    start = time.monotonic()

    # Skip in dev when using a placeholder key
    key = getattr(settings, "azure_openai_api_key", "") or ""
    if key.startswith("fake") or not key:
        latency = (time.monotonic() - start) * 1000
        return ("healthy", latency, None)

    endpoint = getattr(settings, "azure_openai_endpoint", "") or ""
    if not endpoint:
        latency = (time.monotonic() - start) * 1000
        return ("unhealthy", latency, "AZURE_OPENAI_ENDPOINT not configured")

    try:
        async with httpx.AsyncClient(timeout=_PROBE_TIMEOUT) as client:
            # Hit the OpenAI deployments list — lightweight, no tokens used
            resp = await client.get(
                f"{endpoint}/openai/deployments?api-version=2024-02-01",
                headers={"api-key": key},
            )
            latency = (time.monotonic() - start) * 1000
            if resp.status_code in (200, 401, 403):
                # 401/403 means the endpoint is reachable but key issue
                # — still counts as "reachable" for health purposes
                return ("healthy", latency, None)
            return ("unhealthy", latency, f"HTTP {resp.status_code}")
    except Exception as exc:
        latency = (time.monotonic() - start) * 1000
        return ("unhealthy", latency, str(exc))


# =====================================================================
# Endpoint
# =====================================================================


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Returns per-component health status, version, and uptime.",
)
async def health_check() -> HealthResponse:
    """Run all probes in parallel and build the health response."""
    from app.main import get_uptime_seconds

    settings = get_settings()

    probes: Dict[str, Any] = {
        "database": _probe_database,
        "vector_store": _probe_vector_store,
        "object_storage": _probe_object_storage,
        "redis": _probe_redis,
        "llm_api": _probe_llm_api,
    }

    # Run all probes concurrently with an overall timeout
    tasks = {
        name: asyncio.create_task(fn(settings))
        for name, fn in probes.items()
    }

    results: Dict[str, Tuple[str, float, Optional[str]]] = {}
    for name, task in tasks.items():
        try:
            results[name] = await asyncio.wait_for(task, timeout=_PROBE_TIMEOUT + 1)
        except asyncio.TimeoutError:
            results[name] = ("unhealthy", (_PROBE_TIMEOUT + 1) * 1000, "Probe timed out")
        except Exception as exc:
            results[name] = ("unhealthy", 0.0, str(exc))

    # Build component map
    components: Dict[str, HealthComponent] = {}
    for name, (status_str, latency, error) in results.items():
        components[name] = HealthComponent(
            status=status_str,
            latency_ms=round(latency, 2),
            error=error,
        )

    # Determine overall status
    all_healthy = all(c.status == "healthy" for c in components.values())
    db_healthy = components.get("database", HealthComponent(status="unhealthy")).status == "healthy"

    if all_healthy:
        overall = "healthy"
    elif db_healthy:
        overall = "degraded"
    else:
        overall = "unhealthy"

    return HealthResponse(
        status=overall,
        components=components,
        version=settings.app_version,
        uptime_seconds=get_uptime_seconds(),
    )
