"""
Async SQLAlchemy session factory.

Provides the async engine and session maker used by FastAPI dependencies
and background workers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import Settings, get_settings

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


def build_async_engine(settings: Settings | None = None):
    """Create an async SQLAlchemy engine from application settings."""
    if settings is None:
        settings = get_settings()

    return create_async_engine(
        settings.database_url,  # type: ignore[arg-type]
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,
        pool_recycle=300,
        echo=settings.is_development,
    )


def build_async_session_factory(
    settings: Settings | None = None,
) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory bound to the engine."""
    engine = build_async_engine(settings)
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


# Module-level defaults — lazily initialised via create_app() lifespan
_engine = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_engine(settings: Settings) -> None:
    """Initialise the module-level engine and session factory (called at startup)."""
    global _engine, _async_session_factory
    _engine = build_async_engine(settings)
    _async_session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def dispose_engine() -> None:
    """Dispose the module-level engine (called at shutdown)."""
    global _engine, _async_session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _async_session_factory = None


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the module-level session factory. Must be called after init_engine()."""
    if _async_session_factory is None:
        raise RuntimeError(
            "Database engine not initialised. Call init_engine() first."
        )
    return _async_session_factory


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async session — use as a FastAPI dependency or async context manager.

    Transaction boundary: auto-commits on successful exit, rolls back on
    exception.  All API endpoint handlers rely on this for their commit
    semantics — they should *not* call ``session.commit()`` themselves.
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()   # TX: auto-commit on success
        except Exception:
            await session.rollback()  # TX: auto-rollback on failure
            raise
