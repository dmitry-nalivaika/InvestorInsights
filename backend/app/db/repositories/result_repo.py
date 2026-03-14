# filepath: backend/app/db/repositories/result_repo.py
"""Analysis result data access layer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.models.result import AnalysisResult
from app.observability.logging import get_logger

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


class ResultRepository:
    """Async repository for AnalysisResult CRUD and queries."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, **kwargs: Any) -> AnalysisResult:
        """Insert a new analysis result."""
        result = AnalysisResult(**kwargs)
        self._session.add(result)
        await self._session.flush()
        await self._session.refresh(result)
        return result

    async def get_by_id(self, result_id: uuid.UUID) -> AnalysisResult | None:
        """Fetch a result by ID with company and profile relationships."""
        stmt = (
            select(AnalysisResult)
            .options(
                selectinload(AnalysisResult.company),
                selectinload(AnalysisResult.profile),
            )
            .where(AnalysisResult.id == result_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_results(
        self,
        *,
        company_id: uuid.UUID | None = None,
        profile_id: uuid.UUID | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[AnalysisResult], int]:
        """List analysis results with optional filters and pagination."""
        base = select(AnalysisResult)
        count_base = select(func.count()).select_from(AnalysisResult)

        if company_id is not None:
            base = base.where(AnalysisResult.company_id == company_id)
            count_base = count_base.where(AnalysisResult.company_id == company_id)
        if profile_id is not None:
            base = base.where(AnalysisResult.profile_id == profile_id)
            count_base = count_base.where(AnalysisResult.profile_id == profile_id)

        total_result = await self._session.execute(count_base)
        total = total_result.scalar_one()

        stmt = (
            base
            .options(
                selectinload(AnalysisResult.company),
                selectinload(AnalysisResult.profile),
            )
            .order_by(AnalysisResult.run_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        items = list(result.scalars().all())
        return items, total
