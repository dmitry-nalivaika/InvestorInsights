# filepath: backend/app/services/financial_service.py
"""Financial data business logic layer.

Handles XBRL data extraction, financial statement storage,
and retrieval for the financials API.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any

from app.api.middleware.error_handler import NotFoundError, ValidationError
from app.clients.sec_client import SECEdgarClient, get_sec_client
from app.db.repositories.financial_repo import FinancialRepository
from app.observability.logging import get_logger
from app.xbrl.mapper import map_company_facts

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.financial import FinancialStatement

logger = get_logger(__name__)


class FinancialService:
    """Business logic for financial data management."""

    def __init__(
        self,
        session: AsyncSession,
        sec_client: SECEdgarClient | None = None,
    ) -> None:
        self._repo = FinancialRepository(session)
        self._session = session
        self._sec: SECEdgarClient | None = sec_client

    @property
    def sec_client(self) -> SECEdgarClient:
        if self._sec is None:
            self._sec = get_sec_client()
        return self._sec

    # ── XBRL extraction (T303-T305) ──────────────────────────────

    async def extract_and_store_financials(
        self,
        company_id: uuid.UUID,
        cik: str,
        *,
        document_id: uuid.UUID | None = None,
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> int:
        """Fetch XBRL data from SEC and store as financial statements.

        Args:
            company_id: Company UUID.
            cik: Company CIK (10-digit zero-padded).
            document_id: Optional associated document UUID.
            start_year: Filter periods from this year.
            end_year: Filter periods up to this year.

        Returns:
            Number of financial periods stored/updated.
        """
        if not cik:
            logger.warning(
                "Cannot extract financials: no CIK",
                company_id=str(company_id),
            )
            return 0

        try:
            raw_facts = await self.sec_client.get_company_facts(cik)
        except Exception as exc:
            logger.warning(
                "Failed to fetch XBRL data from SEC",
                company_id=str(company_id),
                cik=cik,
                error=str(exc),
            )
            return 0

        periods = map_company_facts(
            raw_facts,
            start_year=start_year,
            end_year=end_year,
        )

        stored_count = 0
        for period in periods:
            try:
                period_end = date.fromisoformat(period["period_end_date"])
                statement_data = {
                    "income_statement": period.get("income_statement", {}),
                    "balance_sheet": period.get("balance_sheet", {}),
                    "cash_flow": period.get("cash_flow", {}),
                }

                await self._repo.upsert(
                    company_id=company_id,
                    fiscal_year=period["fiscal_year"],
                    fiscal_quarter=period["fiscal_quarter"],
                    period_end_date=period_end,
                    statement_data=statement_data,
                    source="xbrl_api",
                    document_id=document_id,
                    raw_xbrl_data=period,
                )
                stored_count += 1
            except Exception as exc:
                logger.warning(
                    "Failed to store financial period",
                    company_id=str(company_id),
                    fiscal_year=period.get("fiscal_year"),
                    error=str(exc),
                )

        logger.info(
            "Financial data extracted and stored",
            company_id=str(company_id),
            periods_stored=stored_count,
        )
        return stored_count

    # ── Read ─────────────────────────────────────────────────────

    async def list_financials(
        self,
        company_id: uuid.UUID,
        *,
        period_type: str | None = None,
        sort_order: str = "desc",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[FinancialStatement], int]:
        """Return a paginated list of financial statements."""
        return await self._repo.list_by_company(
            company_id=company_id,
            period_type=period_type,
            sort_order=sort_order,
            limit=limit,
            offset=offset,
        )

    async def get_financials_for_export(
        self,
        company_id: uuid.UUID,
        *,
        period_type: str | None = None,
    ) -> list[FinancialStatement]:
        """Return all financial statements for CSV export (no pagination)."""
        statements, _ = await self._repo.list_by_company(
            company_id=company_id,
            period_type=period_type,
            sort_order="asc",
            limit=1000,
            offset=0,
        )
        return statements
