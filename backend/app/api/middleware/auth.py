# filepath: backend/app/api/middleware/auth.py
"""
API key authentication.

V1 auth uses a static API key transmitted via the ``X-API-Key`` header.
Constant-time comparison prevents timing attacks (NFR-300).

The key is loaded from ``Settings.api_key`` which is sourced from the
``API_KEY`` env var (populated from Azure Key Vault in production).

Usage:
    The ``require_api_key`` dependency is attached to the top-level
    ``api_router`` so it applies to *all* ``/api/v1/*`` endpoints.
    The ``/api/v1/health`` endpoint opts out by overriding its
    ``dependencies`` list.
"""

from __future__ import annotations

import hmac

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.config import Settings, get_settings

# ── Header scheme ────────────────────────────────────────────────

_api_key_header = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,  # We raise our own 401 for a better error body
    description="API authentication key (V1). Required on all endpoints except /health.",
)


# ── Dependency ───────────────────────────────────────────────────


def _get_settings_for_auth() -> Settings:
    """Thin wrapper so the dependency is easily mockable in tests."""
    return get_settings()


async def require_api_key(
    api_key: str | None = Security(_api_key_header),
    settings: Settings = Depends(_get_settings_for_auth),
) -> str:
    """
    Validate the ``X-API-Key`` header against the configured key.

    Returns the validated key on success.
    Raises 401 if missing or invalid.

    Uses :func:`hmac.compare_digest` for constant-time comparison
    to prevent timing side-channels.
    """
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "status": 401,
                "error": "unauthorized",
                "message": "Missing X-API-Key header",
            },
        )

    # Constant-time comparison (prevents timing attacks)
    if not hmac.compare_digest(api_key, settings.api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "status": 401,
                "error": "unauthorized",
                "message": "Invalid API key",
            },
        )

    return api_key
