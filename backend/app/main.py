"""
FastAPI application factory.

Creates and configures the FastAPI app with:
- Lifespan management (DB engine init/teardown)
- CORS middleware
- API router mounting
- OpenAPI metadata
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.middleware.error_handler import register_error_handlers
from app.api.middleware.rate_limiter import RateLimitMiddleware
from app.api.middleware.request_id import RequestIDMiddleware
from app.api.router import api_router
from app.config import AppEnvironment, Settings, get_settings
from app.db.session import dispose_engine, init_engine
from app.observability.logging import setup_logging

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

# ── Startup time tracking ────────────────────────────────────────
_startup_time: float = 0.0


def get_uptime_seconds() -> int:
    """Return the number of seconds since the application started."""
    if _startup_time == 0.0:
        return 0
    return int(time.time() - _startup_time)


# ── Lifespan ─────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown lifecycle."""
    global _startup_time

    settings: Settings = get_settings()

    # ── Startup ──────────────────────────────────────────────────
    setup_logging(settings)
    init_engine(settings)
    _startup_time = time.time()

    yield

    # ── Shutdown ─────────────────────────────────────────────────
    await dispose_engine()


# ── App Factory ──────────────────────────────────────────────────


def create_app(settings: Settings | None = None) -> FastAPI:
    """
    Create and configure the FastAPI application.

    Args:
        settings: Optional settings override (useful for testing).
                  Falls back to get_settings() singleton.

    Returns:
        Configured FastAPI application instance.
    """
    if settings is None:
        settings = get_settings()

    app = FastAPI(
        title="InvestorInsights API",
        description=(
            "AI-powered SEC filing analysis platform. "
            "RAG chat, financial analysis engine, and document ingestion pipeline."
        ),
        version=settings.app_version,
        lifespan=lifespan,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
    )

    # ── CORS ─────────────────────────────────────────────────────
    _configure_cors(app, settings)

    # ── Middleware (registered in reverse order — outermost first) ─
    # Request ID must be outermost so all downstream middleware/handlers see it.
    # Rate limiter sits between request ID and route handlers.
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(RateLimitMiddleware, settings=settings)

    # ── Routers ──────────────────────────────────────────────────
    # Health is mounted directly on the app (not through api_router)
    # so it bypasses the router-level auth dependency.
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(api_router)

    # ── Error handlers ───────────────────────────────────────────
    register_error_handlers(app)

    return app


def _configure_cors(app: FastAPI, settings: Settings) -> None:
    """Configure CORS based on the environment."""
    if settings.app_env == AppEnvironment.PRODUCTION:
        # Production: restrict to known origins
        allowed_origins = [
            "https://investorinsights.azurecontainerapps.io",
        ]
    else:
        # Development / staging: permissive for local dev
        allowed_origins = [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )


# ── Module-level app instance (used by uvicorn: app.main:app) ────
app = create_app()
