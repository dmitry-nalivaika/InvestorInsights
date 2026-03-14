# filepath: backend/app/services/company_service.py
"""Company business logic layer.

Orchestrates company CRUD operations with SEC EDGAR auto-resolution.
The service sits between the API routes and the data access layer,
encapsulating validation, external lookups, and error mapping.

Key responsibilities:
  - Duplicate ticker detection (→ 409 ConflictError)
  - Auto-resolve metadata from SEC EDGAR on create
  - Map external client errors to application-domain errors
  - Cascade delete orchestration (future: Qdrant cleanup)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.api.middleware.error_handler import (
    ConflictError,
    NotFoundError,
)
from app.clients.sec_client import (
    SECEdgarClient,
    SECEdgarError,
    TickerNotFoundError,
    get_sec_client,
)
from app.db.repositories.company_repo import CompanyRepository
from app.observability.logging import get_logger

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.company import Company
    from app.schemas.company import CompanyCreate, CompanyUpdate

logger = get_logger(__name__)


class CompanyService:
    """Business logic for company management.

    Each instance is scoped to a single request (bound to one
    ``AsyncSession``).  The caller (route handler / dependency)
    is responsible for committing the session on success — the
    repository only flushes, never commits.

    Args:
        session: The async database session for this request.
        sec_client: Optional SEC EDGAR client override (for testing).
    """

    def __init__(
        self,
        session: AsyncSession,
        sec_client: SECEdgarClient | None = None,
    ) -> None:
        self._repo = CompanyRepository(session)
        self._sec: SECEdgarClient | None = sec_client

    @property
    def sec_client(self) -> SECEdgarClient:
        """Lazily resolve the SEC EDGAR client singleton."""
        if self._sec is None:
            self._sec = get_sec_client()
        return self._sec

    # ── Create ───────────────────────────────────────────────────

    async def create_company(self, payload: CompanyCreate) -> Company:
        """Register a new company.

        Steps:
            1. Check for duplicate ticker (→ 409)
            2. Resolve metadata from SEC EDGAR (best-effort)
            3. Merge caller-provided fields over resolved defaults
            4. Persist via repository

        Args:
            payload: Validated creation request.

        Returns:
            The newly created Company ORM instance.

        Raises:
            ConflictError: Ticker already registered.
            ExternalServiceError: SEC EDGAR unreachable.
        """
        ticker = payload.ticker  # already uppercased by schema validator

        # 1 ── Duplicate check
        if await self._repo.exists_by_ticker(ticker):
            raise ConflictError(
                f"Company with ticker '{ticker}' already exists"
            )

        # 2 ── Resolve from SEC EDGAR (best-effort)
        sec_metadata = await self._resolve_from_sec(ticker)

        # 3 ── Merge: caller-provided values take precedence
        create_kwargs = self._merge_create_fields(payload, sec_metadata)

        # 4 ── Persist
        company = await self._repo.create(**create_kwargs)
        logger.info(
            "Company registered",
            company_id=str(company.id),
            ticker=ticker,
            sec_resolved=sec_metadata is not None,
        )
        return company

    # ── Read ─────────────────────────────────────────────────────

    async def get_company(self, company_id: uuid.UUID) -> Company:
        """Fetch a single company by ID.

        Raises:
            NotFoundError: If the company does not exist.
        """
        company = await self._repo.get_by_id(company_id)
        if company is None:
            raise NotFoundError(entity="Company", entity_id=str(company_id))
        return company

    async def get_company_by_ticker(self, ticker: str) -> Company:
        """Fetch a company by ticker symbol.

        Raises:
            NotFoundError: If no company matches the ticker.
        """
        company = await self._repo.get_by_ticker(ticker)
        if company is None:
            raise NotFoundError(
                entity="Company",
                entity_id=ticker,
            )
        return company

    async def list_companies(
        self,
        *,
        search: str | None = None,
        sector: str | None = None,
        sort_by: str = "ticker",
        sort_order: str = "asc",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Company], int]:
        """Return a paginated, filtered list of companies.

        Returns:
            Tuple of (companies, total_count).
        """
        return await self._repo.list(
            search=search,
            sector=sector,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
            offset=offset,
        )

    # ── Summary stats (T105) ────────────────────────────────────

    async def get_bulk_summary_stats(
        self,
        company_ids: list[uuid.UUID],
    ) -> dict[uuid.UUID, dict[str, Any]]:
        """Return doc_count / latest_filing_date / readiness_pct for a batch of companies."""
        return await self._repo.get_bulk_summary_stats(company_ids)

    async def get_detail_summary(
        self,
        company_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Return rich summary (documents, financials, sessions) for company detail."""
        return await self._repo.get_detail_summary(company_id)

    # ── Update ───────────────────────────────────────────────────

    async def update_company(
        self,
        company_id: uuid.UUID,
        payload: CompanyUpdate,
    ) -> Company:
        """Apply a partial update to an existing company.

        Only non-None fields in ``payload`` are written.

        Raises:
            NotFoundError: If the company does not exist.
        """
        company = await self.get_company(company_id)  # raises NotFoundError

        update_data = payload.model_dump(exclude_unset=True)
        if not update_data:
            return company  # nothing to change

        company = await self._repo.update(company, **update_data)
        logger.info(
            "Company updated",
            company_id=str(company_id),
            fields=list(update_data.keys()),
        )
        return company

    # ── Delete ───────────────────────────────────────────────────

    async def delete_company(self, company_id: uuid.UUID) -> None:
        """Delete a company and all associated data.

        The ORM cascade (``delete-orphan``) handles related
        documents, sessions, analysis results, and chunks within
        the same transaction.  The caller must commit the session.

        Future: add Qdrant vector cleanup before the DB delete.

        Raises:
            NotFoundError: If the company does not exist.
        """
        company = await self.get_company(company_id)  # raises NotFoundError

        # TODO (T106): Qdrant vector cleanup for all company chunks
        # await self._cleanup_vectors(company)

        await self._repo.delete(company)
        logger.info(
            "Company deleted",
            company_id=str(company_id),
            ticker=company.ticker,
        )

    # ── SEC resolution (private) ─────────────────────────────────

    async def _resolve_from_sec(
        self, ticker: str
    ) -> dict[str, Any] | None:
        """Best-effort ticker resolution via SEC EDGAR.

        Returns the metadata dict on success, or ``None`` if the
        ticker isn't found or SEC EDGAR is unreachable.  Create
        proceeds either way — the user can fill in metadata later.
        """
        try:
            metadata = await self.sec_client.resolve_ticker(ticker)
            logger.info(
                "SEC EDGAR resolved ticker",
                ticker=ticker,
                cik=metadata.get("cik"),
                name=metadata.get("name"),
            )
            return metadata
        except TickerNotFoundError:
            logger.warning(
                "Ticker not found on SEC EDGAR — proceeding without metadata",
                ticker=ticker,
            )
            return None
        except (SECEdgarError, Exception) as exc:
            logger.warning(
                "SEC EDGAR resolution failed — proceeding without metadata",
                ticker=ticker,
                error=str(exc),
            )
            return None

    # ── Field merging (private) ──────────────────────────────────

    @staticmethod
    def _merge_create_fields(
        payload: CompanyCreate,
        sec_metadata: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Build the keyword args for ``repo.create()``.

        Priority:
            1. Caller-supplied value (from ``payload``)
            2. SEC-resolved value
            3. Fallback default
        """
        sec = sec_metadata or {}

        # Name: use caller's if provided, else SEC-resolved, else ticker
        name = payload.name or sec.get("name") or payload.ticker

        # CIK: caller's if provided, else SEC-resolved
        cik = payload.cik or sec.get("cik")

        # Sector / industry: map from SIC description if not provided
        sector = payload.sector or sec.get("sic_description") or None
        industry = payload.industry or None

        # Store full SEC metadata blob for reference
        extra_metadata: dict[str, Any] | None = None
        if sec:
            extra_metadata = {
                "sec_resolved": True,
                "sic": sec.get("sic"),
                "sic_description": sec.get("sic_description"),
                "state_of_incorporation": sec.get("state_of_incorporation"),
                "fiscal_year_end": sec.get("fiscal_year_end"),
                "entity_type": sec.get("entity_type"),
                "exchanges": sec.get("exchanges", []),
            }

        return {
            "ticker": payload.ticker,
            "name": name,
            "cik": cik,
            "sector": sector,
            "industry": industry,
            "metadata_": extra_metadata,
        }
