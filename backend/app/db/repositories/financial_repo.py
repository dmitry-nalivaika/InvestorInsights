# filepath: backend/app/db/repositories/financial_repo.py
"""Financial statement data access layer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from app.models.financial import FinancialStatement
from app.observability.logging import get_logger

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


class FinancialRepository:
    """Async repository for FinancialStatement CRUD and queries."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, **kwargs: Any) -> FinancialStatement:
        """Insert a new financial statement and flush."""
        stmt = FinancialStatement(**kwargs)
        self._session.add(stmt)
        await self._session.flush()
        await self._session.refresh(stmt)
        return stmt

    async def upsert(
        self,
        company_id: uuid.UUID,
        fiscal_year: int,
        fiscal_quarter: int | None,
        **kwargs: Any,
    ) -> FinancialStatement:
        """Insert or update a financial statement for a given period."""
        existing = await self.get_by_period(company_id, fiscal_year, fiscal_quarter)
        if existing:
            for key, value in kwargs.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)
            await self._session.flush()
            await self._session.refresh(existing)
            return existing
        return await self.create(
            company_id=company_id,
            fiscal_year=fiscal_year,
            fiscal_quarter=fiscal_quarter,
            **kwargs,
        )

    async def get_by_period(
        self,
        company_id: uuid.UUID,
        fiscal_year: int,
        fiscal_quarter: int | None,
    ) -> FinancialStatement | None:
        """Fetch a financial statement for a specific period."""
        stmt = select(FinancialStatement).where(
            FinancialStatement.company_id == company_id,
            FinancialStatement.fiscal_year == fiscal_year,
        )
        if fiscal_quarter is not None:
            stmt = stmt.where(FinancialStatement.fiscal_quarter == fiscal_quarter)
        else:
            stmt = stmt.where(FinancialStatement.fiscal_quarter.is_(None))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_company(
        self,
        company_id: uuid.UUID,
        *,
        period_type: str | None = None,
        sort_order: str = "desc",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[FinancialStatement], int]:
        """Return a paginated list of financial statements for a company."""
        base_stmt = select(FinancialStatement).where(
            FinancialStatement.company_id == company_id,
        )
        count_stmt = (
            select(func.count())
            .select_from(FinancialStatement)
            .where(FinancialStatement.company_id == company_id)
        )

        if period_type == "annual":
            base_stmt = base_stmt.where(FinancialStatement.fiscal_quarter.is_(None))
            count_stmt = count_stmt.where(FinancialStatement.fiscal_quarter.is_(None))
        elif period_type == "quarterly":
            base_stmt = base_stmt.where(FinancialStatement.fiscal_quarter.isnot(None))
            count_stmt = count_stmt.where(FinancialStatement.fiscal_quarter.isnot(None))

        total_result = await self._session.execute(count_stmt)
        total = total_result.scalar_one()

        if sort_order == "asc":
            base_stmt = base_stmt.order_by(
                FinancialStatement.fiscal_year.asc(),
                FinancialStatement.fiscal_quarter.asc(),
            )
        else:
            base_stmt = base_stmt.order_by(
                FinancialStatement.fiscal_year.desc(),
                FinancialStatement.fiscal_quarter.desc(),
            )

        base_stmt = base_stmt.limit(limit).offset(offset)
        result = await self._session.execute(base_stmt)
        return list(result.scalars().all()), total

    async def count_by_company(self, company_id: uuid.UUID) -> int:
        """Count financial statements for a company."""
        stmt = (
            select(func.count())
            .select_from(FinancialStatement)
            .where(FinancialStatement.company_id == company_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def delete_by_company(self, company_id: uuid.UUID) -> int:
        """Delete all financial statements for a company. Returns count deleted."""
        from sqlalchemy import delete

        stmt = delete(FinancialStatement).where(
            FinancialStatement.company_id == company_id,
        )
        result = await self._session.execute(stmt)
        return result.rowcount or 0
