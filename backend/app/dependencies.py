"""
FastAPI dependency injection.

Central location for all injectable dependencies used across route handlers.
Dependencies are resolved per-request by FastAPI's DI framework.
"""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.storage_client import StorageClient, get_storage_client
from app.config import Settings, get_settings
from app.db.session import get_async_session

# ── Settings ─────────────────────────────────────────────────────


def get_current_settings() -> Settings:
    """Return the cached application settings singleton."""
    return get_settings()


SettingsDep = Annotated[Settings, Depends(get_current_settings)]

# ── Database Session ─────────────────────────────────────────────


async def get_db(
    request: Request,
) -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session scoped to the request lifecycle."""
    async for session in get_async_session():
        yield session


DbSessionDep = Annotated[AsyncSession, Depends(get_db)]

# ── Object Storage ───────────────────────────────────────────────


def get_storage() -> StorageClient:
    """Return the global StorageClient singleton."""
    return get_storage_client()


StorageDep = Annotated[StorageClient, Depends(get_storage)]
