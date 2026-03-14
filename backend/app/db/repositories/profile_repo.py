# filepath: backend/app/db/repositories/profile_repo.py
"""Analysis profile data access layer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from app.models.criterion import AnalysisCriterion
from app.models.profile import AnalysisProfile
from app.observability.logging import get_logger

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


class ProfileRepository:
    """Async repository for AnalysisProfile and AnalysisCriterion CRUD."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── Profile CRUD ─────────────────────────────────────────────

    async def create(self, **kwargs: Any) -> AnalysisProfile:
        """Create a new analysis profile."""
        criteria_data = kwargs.pop("criteria", [])
        profile = AnalysisProfile(**kwargs)
        self._session.add(profile)
        await self._session.flush()

        for i, crit_data in enumerate(criteria_data):
            crit_data["profile_id"] = profile.id
            if "sort_order" not in crit_data:
                crit_data["sort_order"] = i
            crit = AnalysisCriterion(**crit_data)
            self._session.add(crit)

        await self._session.flush()
        await self._session.refresh(profile, attribute_names=["criteria"])
        return profile

    async def get_by_id(self, profile_id: uuid.UUID) -> AnalysisProfile | None:
        """Fetch a profile by ID with criteria eagerly loaded."""
        from sqlalchemy.orm import selectinload

        stmt = (
            select(AnalysisProfile)
            .options(selectinload(AnalysisProfile.criteria))
            .where(AnalysisProfile.id == profile_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> AnalysisProfile | None:
        """Fetch a profile by name."""
        stmt = select(AnalysisProfile).where(AnalysisProfile.name == name)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AnalysisProfile], int]:
        """List profiles with pagination."""
        count_stmt = select(func.count()).select_from(AnalysisProfile)
        total_result = await self._session.execute(count_stmt)
        total = total_result.scalar_one()

        stmt = (
            select(AnalysisProfile)
            .order_by(AnalysisProfile.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        profiles = list(result.scalars().all())
        return profiles, total

    async def update(
        self,
        profile: AnalysisProfile,
        *,
        updates: dict[str, Any],
        new_criteria: list[dict[str, Any]] | None = None,
    ) -> AnalysisProfile:
        """Update a profile and optionally replace all criteria.

        Increments version when criteria are replaced.
        """
        for key, value in updates.items():
            if hasattr(profile, key):
                setattr(profile, key, value)

        if new_criteria is not None:
            # Delete existing criteria
            for crit in list(profile.criteria):
                await self._session.delete(crit)
            await self._session.flush()

            # Add new criteria
            for i, crit_data in enumerate(new_criteria):
                crit_data["profile_id"] = profile.id
                if "sort_order" not in crit_data:
                    crit_data["sort_order"] = i
                crit = AnalysisCriterion(**crit_data)
                self._session.add(crit)

            # Increment version
            profile.version = profile.version + 1

        await self._session.flush()
        await self._session.refresh(profile, attribute_names=["criteria"])
        return profile

    async def delete(self, profile: AnalysisProfile) -> None:
        """Delete a profile (cascades to criteria)."""
        await self._session.delete(profile)
        await self._session.flush()

    async def get_default(self) -> AnalysisProfile | None:
        """Fetch the default profile, if any."""
        from sqlalchemy.orm import selectinload

        stmt = (
            select(AnalysisProfile)
            .options(selectinload(AnalysisProfile.criteria))
            .where(AnalysisProfile.is_default.is_(True))
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
