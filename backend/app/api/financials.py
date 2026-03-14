# filepath: backend/app/api/financials.py
"""Financial data API routes.

Endpoints:
  GET /api/v1/companies/{company_id}/financials        — List financial periods
  GET /api/v1/companies/{company_id}/financials/export  — CSV export
"""

from __future__ import annotations

import csv
import io
import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.api.middleware.error_handler import NotFoundError
from app.dependencies import DbSessionDep
from app.observability.logging import get_logger
from app.schemas.financial import FinancialPeriod, FinancialsResponse
from app.services.financial_service import FinancialService

logger = get_logger(__name__)

router = APIRouter(prefix="/companies/{company_id}/financials", tags=["financials"])


def _get_financial_service(session: DbSessionDep) -> FinancialService:
    """Build a request-scoped FinancialService."""
    return FinancialService(session)


FinancialServiceDep = Depends(_get_financial_service)


@router.get(
    "",
    response_model=FinancialsResponse,
    summary="List financial data for a company",
)
async def list_financials(
    company_id: uuid.UUID,
    period_type: str | None = Query(None, description="Filter: 'annual' or 'quarterly'"),
    sort_order: str = Query("desc", description="Sort order: asc or desc"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    service: FinancialService = FinancialServiceDep,
) -> FinancialsResponse:
    """Return financial data periods for a company."""
    # Verify company exists
    from app.db.repositories.company_repo import CompanyRepository

    company_repo = CompanyRepository(service._session)
    company = await company_repo.get_by_id(company_id)
    if company is None:
        raise NotFoundError(entity="Company", entity_id=str(company_id))

    statements, total = await service.list_financials(
        company_id=company_id,
        period_type=period_type,
        sort_order=sort_order,
        limit=limit,
        offset=offset,
    )

    periods = []
    for stmt in statements:
        data = stmt.statement_data or {}
        periods.append(FinancialPeriod(
            fiscal_year=stmt.fiscal_year,
            fiscal_quarter=stmt.fiscal_quarter,
            period_end_date=stmt.period_end_date,
            currency=stmt.currency,
            source=stmt.source,
            income_statement=data.get("income_statement", {}),
            balance_sheet=data.get("balance_sheet", {}),
            cash_flow=data.get("cash_flow", {}),
        ))

    return FinancialsResponse(company_id=company_id, periods=periods)


@router.get(
    "/export",
    summary="Export financial data as CSV",
    response_class=StreamingResponse,
)
async def export_financials_csv(
    company_id: uuid.UUID,
    period_type: str | None = Query(None, description="Filter: 'annual' or 'quarterly'"),
    service: FinancialService = FinancialServiceDep,
) -> StreamingResponse:
    """Export financial data as a downloadable CSV file."""
    from app.db.repositories.company_repo import CompanyRepository

    company_repo = CompanyRepository(service._session)
    company = await company_repo.get_by_id(company_id)
    if company is None:
        raise NotFoundError(entity="Company", entity_id=str(company_id))

    statements = await service.get_financials_for_export(
        company_id=company_id,
        period_type=period_type,
    )

    # Build CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # Collect all field names across all statements
    all_fields: set[str] = set()
    for stmt in statements:
        data = stmt.statement_data or {}
        for section in ("income_statement", "balance_sheet", "cash_flow"):
            section_data = data.get(section, {})
            for field_name in section_data:
                all_fields.add(f"{section}.{field_name}")

    sorted_fields = sorted(all_fields)

    # Header row
    header = ["fiscal_year", "fiscal_quarter", "period_end_date", "currency"]
    header.extend(sorted_fields)
    writer.writerow(header)

    # Data rows
    for stmt in statements:
        data = stmt.statement_data or {}
        row = [
            stmt.fiscal_year,
            stmt.fiscal_quarter or "",
            str(stmt.period_end_date),
            stmt.currency,
        ]
        for field_key in sorted_fields:
            section, field_name = field_key.split(".", 1)
            value = data.get(section, {}).get(field_name, "")
            row.append(value)
        writer.writerow(row)

    output.seek(0)
    ticker = company.ticker.lower()
    filename = f"{ticker}_financials"
    if period_type:
        filename += f"_{period_type}"
    filename += ".csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
