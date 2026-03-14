# filepath: backend/app/scripts/seed_defaults.py
"""Seed default analysis profile (Quality Value Investor, 15 criteria).

Usage:
    python -m app.scripts.seed_defaults

Called by ``scripts/seed.sh`` and ``scripts/reset.sh``.

Task: T514
"""

from __future__ import annotations

import asyncio
import sys

from app.config import get_settings
from app.db.session import build_async_engine
from app.observability.logging import get_logger
from app.services.analysis_service import AnalysisService

logger = get_logger(__name__)


async def _seed() -> None:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    settings = get_settings()
    engine = build_async_engine(settings)
    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    try:
        async with session_factory() as session:
            svc = AnalysisService(session, openai_client=None)
            profile = await svc.seed_default_profile()
            await session.commit()

            if profile:
                logger.info(
                    "✅ Seeded default profile '%s' with %d criteria",
                    profile.name,
                    len(profile.criteria),
                )
            else:
                logger.info("ℹ️  Default profile already exists — skipped")
    finally:
        await engine.dispose()


def main() -> None:
    """Entry point for ``python -m app.scripts.seed_defaults``."""
    logger.info("🌱 Seeding default analysis profiles …")
    try:
        asyncio.run(_seed())
    except KeyboardInterrupt:
        logger.info("Seed interrupted")
        sys.exit(1)
    except Exception:
        logger.exception("Seed failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
