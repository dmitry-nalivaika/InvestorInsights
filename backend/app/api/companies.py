# filepath: backend/app/api/companies.py
"""Company CRUD API routes.

Endpoints:
  POST   /api/v1/companies               — Register a new company
  GET    /api/v1/companies               — List companies (paginated)
  GET    /api/v1/companies/{company_id}  — Company detail
  PUT    /api/v1/companies/{company_id}  — Partial update
  DELETE /api/v1/companies/{company_id}  — Delete (requires ?confirm=true)
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.middleware.error_handler import ValidationError
from app.api.pagination import PaginationQuery  # noqa: TC001 — runtime dep
from app.dependencies import DbSessionDep  # noqa: TC001 — runtime dep
from app.observability.logging import get_logger
from app.schemas.company import (
    CompanyCreate,
    CompanyDetail,
    CompanyList,
    CompanyRead,
    CompanyUpdate,
)
from app.services.company_service import CompanyService

logger = get_logger(__name__)

router = APIRouter(prefix="/companies", tags=["companies"])


# ── Helpers ──────────────────────────────────────────────────────


def _get_company_service(session: DbSessionDep) -> CompanyService:
    """Build a request-scoped CompanyService."""
    return CompanyService(session)


CompanyServiceDep = Depends(_get_company_service)


# ── POST /companies ──────────────────────────────────────────────


@router.post(
    "",
    response_model=CompanyRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new company",
    description="Register a company by ticker. Metadata is auto-resolved from SEC EDGAR.",
)
async def create_company(
    payload: CompanyCreate,
    service: CompanyService = CompanyServiceDep,
) -> CompanyRead:
    """Create a new company with optional SEC EDGAR auto-resolution."""
    company = await service.create_company(payload)
    return CompanyRead.model_validate(company)


# ── GET /companies ───────────────────────────────────────────────


@router.get(
    "",
    response_model=CompanyList,
    summary="List companies",
    description="Paginated company list with search, sector filter, and sorting.",
)
async def list_companies(
    pagination: PaginationQuery = Depends(),
    search: str | None = Query(None, description="Search ticker or name"),
    sector: str | None = Query(None, description="Filter by sector"),
    service: CompanyService = CompanyServiceDep,
) -> CompanyList:
    """Return a paginated list of companies."""
    companies, total = await service.list_companies(
        search=search,
        sector=sector,
        sort_by=pagination.sort_by,
        sort_order=pagination.sort_order,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    # Build list items — doc_count / latest_filing_date / readiness_pct
    # are defaults (0 / None / 0.0) until T105 adds summary stats.
    items = [CompanyRead.model_validate(c) for c in companies]
    return CompanyList(
        items=items,
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


# ── GET /companies/{company_id} ─────────────────────────────────


@router.get(
    "/{company_id}",
    response_model=CompanyDetail,
    summary="Get company details",
    description="Detailed company view with document/financial summaries.",
)
async def get_company(
    company_id: uuid.UUID,
    service: CompanyService = CompanyServiceDep,
) -> CompanyDetail:
    """Fetch a single company with summary statistics."""
    company = await service.get_company(company_id)
    # Documents/financials/sessions summaries are defaults until
    # later phases populate them (T105, Phase 4, Phase 5).
    return CompanyDetail.model_validate(company)


# ── PUT /companies/{company_id} ─────────────────────────────────


@router.put(
    "/{company_id}",
    response_model=CompanyRead,
    summary="Update company metadata",
    description="Partial update — only supplied fields are changed.",
)
async def update_company(
    company_id: uuid.UUID,
    payload: CompanyUpdate,
    service: CompanyService = CompanyServiceDep,
) -> CompanyRead:
    """Apply a partial metadata update to a company."""
    company = await service.update_company(company_id, payload)
    return CompanyRead.model_validate(company)


# ── DELETE /companies/{company_id} ───────────────────────────────


@router.delete(
    "/{company_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a company",
    description="Delete a company and ALL associated data. Requires ?confirm=true.",
)
async def delete_company(
    company_id: uuid.UUID,
    confirm: bool = Query(False, description="Must be true to confirm deletion"),
    service: CompanyService = CompanyServiceDep,
) -> Response:
    """Delete a company with cascade cleanup."""
    if not confirm:
        raise ValidationError(
            "Deletion requires confirm=true query parameter",
            details=[{"field": "confirm", "reason": "Must be true"}],
        )
    await service.delete_company(company_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
