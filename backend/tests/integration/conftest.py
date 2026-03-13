# filepath: backend/tests/integration/conftest.py
"""Shared fixtures for integration tests."""

from __future__ import annotations

import os
from typing import Generator

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

# Set required env vars BEFORE any app imports so Settings() doesn't fail.
os.environ.setdefault("API_KEY", "test-api-key-for-integration-tests")
os.environ.setdefault("AZURE_OPENAI_API_KEY", "fake-azure-openai-key")
os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://fake.openai.azure.com")
os.environ.setdefault("AZURE_STORAGE_CONNECTION_STRING", "")
os.environ.setdefault("AZURE_STORAGE_ACCOUNT_NAME", "devstoreaccount1")

from app.api.middleware.auth import require_api_key  # noqa: E402
from app.api.router import api_router  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.main import create_app  # noqa: E402


# ── Test-only stubs ──────────────────────────────────────────────
# These lightweight routes exist so integration tests can exercise
# auth enforcement and health without depending on real feature
# routers (companies, documents, …) that haven't been built yet.
#
# IMPORTANT: The protected stub must be registered on api_router
# **before** create_app() is called, because include_router()
# copies routes at call time.

_protected_stub_registered = False


def _register_protected_stub() -> None:
    """Add /test-protected to the auth-guarded api_router."""
    global _protected_stub_registered  # noqa: PLW0603
    if _protected_stub_registered:
        return
    _has_it = any(
        getattr(r, "path", None) == "/test-protected"
        for r in api_router.routes
    )
    if not _has_it:
        @api_router.get("/test-protected", tags=["test"])
        async def _test_protected_stub() -> dict:
            return {"ok": True}
    _protected_stub_registered = True


def _register_health_stub(app: FastAPI) -> None:
    """Mount a public /api/v1/health on the app (bypasses api_router auth).

    T014 will replace this with the real health endpoint.
    """
    # Check whether a real health route already exists on the app
    for route in app.routes:
        path = getattr(route, "path", "")
        if path == "/api/v1/health":
            return
    health_router = APIRouter(prefix="/api/v1", tags=["system"])

    @health_router.get("/health")
    async def _health_stub() -> dict:
        return {"status": "healthy", "version": "test"}

    app.include_router(health_router)


def _register_error_test_routes(app: FastAPI) -> None:
    """Mount error-triggering test routes used by test_error_handler.py."""
    from tests.integration.test_error_handler import _get_error_test_router

    app.include_router(_get_error_test_router())


# Register the protected stub NOW (module load time, before any
# fixture calls create_app → include_router).
_register_protected_stub()


@pytest.fixture(scope="session")
def app() -> FastAPI:
    """Create the FastAPI application for integration testing."""
    application = create_app()
    _register_health_stub(application)
    _register_error_test_routes(application)
    return application


@pytest.fixture(scope="session")
def api_key() -> str:
    """Return the configured API key for authenticated requests."""
    return get_settings().api_key


@pytest.fixture()
def client(app: FastAPI) -> Generator[TestClient, None, None]:
    """Provide a TestClient that does NOT raise server exceptions."""
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture()
def auth_header(api_key: str) -> dict[str, str]:
    """Provide the X-API-Key header dict for authenticated requests."""
    return {"X-API-Key": api_key}
