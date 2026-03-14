# filepath: backend/app/db/repositories/company_repo.py
"""Company data access layer.

Provides async CRUD operations and query helpers for the Company model.
All database interactions for companies are encapsulated here, keeping
the service layer free of SQLAlchemy imports.

Repository methods accept an ``AsyncSession`` - the caller (service or
dependency) is responsible for transaction management (commit / rollback).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import Select, delete, func, or_, select

from app.models.company import Company
from app.observability.logging import get_logger

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


class CompanyRepository:
    """Async repository for Company CRUD and queries."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── Create ───────────────────────────────────────────────────

    async def create(self, **kwargs: Any) -> Company:
        """Insert a new company and flush to get the generated id.

        Args:
            **kwargs: Column values (ticker, name, cik, sector, etc.)

        Returns:
            The newly created Company instance (with id populated).
        """
        company = Company(**kwargs)
        self._session.add(company)
        await self._session.flush()
        await self._session.refresh(company)
        logger.info(
            "Company created",
            company_id=str(company.id),
            ticker=company.ticker,
        )
        return company

    # ── Read ─────────────────────────────────────────────────────

    async def get_by_id(self, company_id: uuid.UUID) -> Company | None:
        """Fetch a company by primary key.

        Returns:
            The Company or None if not found.
        """
        return await self._session.get(Company, company_id)

    async def get_by_ticker(self, ticker: str) -> Company | None:
        """Fetch a company by its unique ticker symbol (case-insensitive).

        Returns:
            The Company or None if not found.
        """
        stmt = select(Company).where(
            func.upper(Company.ticker) == ticker.upper()
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list(
        self,
        *,
        search: str | None = None,
        sector: str | None = None,
        sort_by: str = "ticker",
        sort_order: str = "asc",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Company], int]:
        """Return a paginated list of companies with optional filters.

        Args:
            search: Case-insensitive substring match on ticker or name.
            sector: Exact match on sector (case-insensitive).
            sort_by: Column to sort by (ticker, name, created_at).
            sort_order: 'asc' or 'desc'.
            limit: Max items to return (1-100).
            offset: Number of items to skip.

        Returns:
            Tuple of (companies, total_count).
        """
        base_stmt = select(Company)
        count_stmt = select(func.count()).select_from(Company)

        # Apply filters
        base_stmt = self._apply_filters(base_stmt, search=search, sector=sector)
        count_stmt = self._apply_count_filters(count_stmt, search=search, sector=sector)

        # Count total matching rows
        total_result = await self._session.execute(count_stmt)
        total = total_result.scalar_one()

        # Sort
        sort_column = self._resolve_sort_column(sort_by)
        if sort_order.lower() == "desc":
            base_stmt = base_stmt.order_by(sort_column.desc())
        else:
            base_stmt = base_stmt.order_by(sort_column.asc())

        # Paginate
        base_stmt = base_stmt.limit(limit).offset(offset)

        result = await self._session.execute(base_stmt)
        companies = list(result.scalars().all())

        return companies, total

    async def exists_by_ticker(self, ticker: str) -> bool:
        """Check whether a company with the given ticker already exists."""
        stmt = (
            select(func.count())
            .select_from(Company)
            .where(func.upper(Company.ticker) == ticker.upper())
        )
        result = await self._session.execute(stmt)
        return (result.scalar_one() or 0) > 0

    # ── Update ───────────────────────────────────────────────────

    async def update(
        self, company: Company, **kwargs: Any
    ) -> Company:
        """Apply partial updates to an existing company.

        Only non-None values in kwargs are applied.

        Args:
            company: The company instance to update.
            **kwargs: Fields to update.

        Returns:
            The updated Company instance.
        """
        for key, value in kwargs.items():
            if value is not None and hasattr(company, key):
                setattr(company, key, value)
        await self._session.flush()
        await self._session.refresh(company)
        logger.info(
            "Company updated",
            company_id=str(company.id),
            fields=list(kwargs.keys()),
        )
        return company

    # ── Delete ───────────────────────────────────────────────────

    async def delete(self, company: Company) -> None:
        """Delete a company (cascade handled by ORM relationships).

        The session must be committed by the caller to finalise.
        """
        company_id = str(company.id)
        ticker = company.ticker
        await self._session.delete(company)
        await self._session.flush()
        logger.info(
            "Company deleted",
            company_id=company_id,
            ticker=ticker,
        )

    async def delete_by_id(self, company_id: uuid.UUID) -> bool:
        """Delete a company by its ID using a bulk DELETE statement.

        Returns:
            True if a row was deleted, False if no matching row.
        """
        stmt = delete(Company).where(Company.id == company_id)
        result = await self._session.execute(stmt)
        deleted = (result.rowcount or 0) > 0
        if deleted:
            logger.info("Company deleted by id", company_id=str(company_id))
        return deleted

    # ── Aggregate helpers (for list endpoint summary stats) ──────

    async def count(self) -> int:
        """Return the total number of companies."""
        stmt = select(func.count()).select_from(Company)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    # ── Private helpers ──────────────────────────────────────────

    @staticmethod
    def _apply_filters(
        stmt: Select[tuple[Company]],
        *,
        search: str | None = None,
        sector: str | None = None,
    ) -> Select[tuple[Company]]:
        """Apply search and sector filters to a select statement."""
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    Company.ticker.ilike(pattern),
                    Company.name.ilike(pattern),
                )
            )
        if sector:
            stmt = stmt.where(func.lower(Company.sector) == sector.lower())
        return stmt

    @staticmethod
    def _apply_count_filters(
        stmt: Select[Any],
        *,
        search: str | None = None,
        sector: str | None = None,
    ) -> Select[Any]:
        """Apply the same filters to a count statement."""
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    Company.ticker.ilike(pattern),
                    Company.name.ilike(pattern),
                )
            )
        if sector:
            stmt = stmt.where(func.lower(Company.sector) == sector.lower())
        return stmt

    @staticmethod
    def _resolve_sort_column(sort_by: str) -> Any:
        """Map a sort_by string to a SQLAlchemy column.

        Defaults to ``Company.ticker`` for unknown values.
        """
        mapping = {
            "ticker": Company.ticker,
            "name": Company.name,
            "created_at": Company.created_at,
        }
        return mapping.get(sort_by, Company.ticker)
