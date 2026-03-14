# filepath: backend/app/api/analysis.py
"""Analysis API routes.

Endpoints:
  POST   /api/v1/analysis/profiles               — Create profile
  GET    /api/v1/analysis/profiles               — List profiles
  GET    /api/v1/analysis/profiles/{profile_id}  — Profile detail
  PUT    /api/v1/analysis/profiles/{profile_id}  — Update profile
  DELETE /api/v1/analysis/profiles/{profile_id}  — Delete profile
  POST   /api/v1/analysis/run                    — Run analysis
  POST   /api/v1/analysis/compare                — Compare companies (ranked)
  GET    /api/v1/analysis/results                — List results
  GET    /api/v1/analysis/results/{result_id}    — Result detail
  GET    /api/v1/analysis/results/{result_id}/export — Export result JSON
  GET    /api/v1/analysis/formulas               — List built-in formulas

Tasks: T504, T509, T512, T513, T517, T600, T601
"""

from __future__ import annotations

import contextlib
import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import JSONResponse

from app.analysis.formulas import ALL_BUILTIN_FORMULAS
from app.analysis.scorer import compute_grade
from app.dependencies import DbSessionDep  # noqa: TC001 - runtime dep for FastAPI DI
from app.observability.logging import get_logger
from app.schemas.analysis import (
    AnalysisResultList,
    AnalysisResultRead,
    AnalysisRunRequest,
    AnalysisRunResponse,
    CompanyComparisonItem,
    CompanyCriterionCell,
    ComparisonRequest,
    ComparisonResponse,
    CriteriaResultItem,
    FormulaInfo,
    FormulaListResponse,
    ProfileCreate,
    ProfileDetail,
    ProfileList,
    ProfileRead,
    ProfileUpdate,
)
from app.services.analysis_service import AnalysisService

logger = get_logger(__name__)

router = APIRouter(prefix="/analysis", tags=["analysis"])


# ── Helpers ──────────────────────────────────────────────────────


def _get_analysis_service(session: DbSessionDep) -> AnalysisService:
    """Build a request-scoped AnalysisService."""
    openai_client = None
    with contextlib.suppress(Exception):
        from app.clients.openai_client import get_openai_client
        openai_client = get_openai_client()
    return AnalysisService(session, openai_client=openai_client)


AnalysisServiceDep = Depends(_get_analysis_service)


# ── Profile CRUD (T504) ─────────────────────────────────────────


@router.post(
    "/profiles",
    response_model=ProfileDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Create an analysis profile",
)
async def create_profile(
    body: ProfileCreate,
    svc: AnalysisService = AnalysisServiceDep,
) -> ProfileDetail:
    criteria_dicts = [c.model_dump() for c in body.criteria]
    profile = await svc.create_profile(
        name=body.name,
        description=body.description,
        is_default=body.is_default,
        criteria=criteria_dicts,
    )
    return _profile_to_detail(profile)


@router.get(
    "/profiles",
    response_model=ProfileList,
    summary="List analysis profiles",
)
async def list_profiles(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    svc: AnalysisService = AnalysisServiceDep,
) -> ProfileList:
    profiles, total = await svc.list_profiles(limit=limit, offset=offset)
    return ProfileList(
        items=[_profile_to_read(p) for p in profiles],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/profiles/{profile_id}",
    response_model=ProfileDetail,
    summary="Get profile with all criteria",
)
async def get_profile(
    profile_id: uuid.UUID,
    svc: AnalysisService = AnalysisServiceDep,
) -> ProfileDetail:
    profile = await svc.get_profile(profile_id)
    return _profile_to_detail(profile)


@router.put(
    "/profiles/{profile_id}",
    response_model=ProfileDetail,
    summary="Update an analysis profile",
)
async def update_profile(
    profile_id: uuid.UUID,
    body: ProfileUpdate,
    svc: AnalysisService = AnalysisServiceDep,
) -> ProfileDetail:
    criteria_dicts = [c.model_dump() for c in body.criteria] if body.criteria else None
    profile = await svc.update_profile(
        profile_id,
        name=body.name,
        description=body.description,
        is_default=body.is_default,
        criteria=criteria_dicts,
    )
    return _profile_to_detail(profile)


@router.delete(
    "/profiles/{profile_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an analysis profile",
)
async def delete_profile(
    profile_id: uuid.UUID,
    svc: AnalysisService = AnalysisServiceDep,
) -> Response:
    await svc.delete_profile(profile_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Analysis run (T509) ─────────────────────────────────────────


@router.post(
    "/run",
    response_model=AnalysisRunResponse,
    summary="Run analysis for companies against a profile",
)
async def run_analysis(
    body: AnalysisRunRequest,
    svc: AnalysisService = AnalysisServiceDep,
) -> AnalysisRunResponse:
    results = await svc.run_analysis(
        company_ids=body.company_ids,
        profile_id=body.profile_id,
        generate_summary=body.generate_summary,
    )
    return AnalysisRunResponse(
        results=[_result_to_read(r) for r in results],
    )


# ── Multi-company comparison (T600-T601) ─────────────────────────


@router.post(
    "/compare",
    response_model=ComparisonResponse,
    summary="Compare companies against the same profile (ranked)",
)
async def compare_companies(
    body: ComparisonRequest,
    svc: AnalysisService = AnalysisServiceDep,
) -> ComparisonResponse:
    comparison = await svc.compare_companies(
        company_ids=body.company_ids,
        profile_id=body.profile_id,
        generate_summary=body.generate_summary,
    )
    return _build_comparison_response(comparison)


# ── Results retrieval (T512) ────────────────────────────────────


@router.get(
    "/results",
    response_model=AnalysisResultList,
    summary="List past analysis results",
)
async def list_results(
    company_id: uuid.UUID | None = Query(None),
    profile_id: uuid.UUID | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    svc: AnalysisService = AnalysisServiceDep,
) -> AnalysisResultList:
    results, total = await svc.list_results(
        company_id=company_id,
        profile_id=profile_id,
        limit=limit,
        offset=offset,
    )
    return AnalysisResultList(
        items=[_result_to_read(r) for r in results],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/results/{result_id}",
    response_model=AnalysisResultRead,
    summary="Get a specific analysis result",
)
async def get_result(
    result_id: uuid.UUID,
    svc: AnalysisService = AnalysisServiceDep,
) -> AnalysisResultRead:
    result = await svc.get_result(result_id)
    return _result_to_read(result)


# ── Export (T517) ────────────────────────────────────────────────


@router.get(
    "/results/{result_id}/export",
    summary="Export analysis result as downloadable JSON",
)
async def export_result(
    result_id: uuid.UUID,
    svc: AnalysisService = AnalysisServiceDep,
) -> Response:
    result = await svc.get_result(result_id)
    result_data = _result_to_read(result)

    ticker = result_data.company_ticker or "unknown"
    profile_name = (
        result.profile.name.replace(" ", "_").lower()
        if result.profile
        else "profile"
    )
    run_date = result.run_at.strftime("%Y%m%d") if result.run_at else "unknown"
    filename = f"{ticker}_{profile_name}_{run_date}.json"

    return JSONResponse(
        content=result_data.model_dump(mode="json"),
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


# ── Formulas reference (T513) ───────────────────────────────────


@router.get(
    "/formulas",
    response_model=FormulaListResponse,
    summary="List all available built-in formulas",
)
async def list_formulas() -> FormulaListResponse:
    formulas = [
        FormulaInfo(
            name=f.name,
            category=f.category,
            description=f.description,
            required_fields=f.required_fields,
            example=f.example,
        )
        for f in ALL_BUILTIN_FORMULAS
    ]
    return FormulaListResponse(formulas=formulas)


# ── Response builders ────────────────────────────────────────────


def _profile_to_read(profile: object) -> ProfileRead:
    """Convert an AnalysisProfile ORM object to ProfileRead schema."""
    return ProfileRead(
        id=profile.id,
        name=profile.name,
        description=profile.description,
        is_default=profile.is_default,
        version=profile.version,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


def _profile_to_detail(profile: object) -> ProfileDetail:
    """Convert an AnalysisProfile ORM object to ProfileDetail schema."""
    from app.schemas.analysis import CriterionRead

    criteria = [
        CriterionRead(
            id=c.id,
            profile_id=c.profile_id,
            name=c.name,
            category=c.category,
            description=c.description,
            formula=c.formula,
            is_custom_formula=c.is_custom_formula,
            comparison=c.comparison,
            threshold_value=c.threshold_value,
            threshold_low=c.threshold_low,
            threshold_high=c.threshold_high,
            weight=c.weight,
            lookback_years=c.lookback_years,
            enabled=c.enabled,
            sort_order=c.sort_order,
            created_at=c.created_at,
        )
        for c in profile.criteria
    ]

    return ProfileDetail(
        id=profile.id,
        name=profile.name,
        description=profile.description,
        is_default=profile.is_default,
        version=profile.version,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
        criteria=criteria,
    )


def _result_to_read(result: object) -> AnalysisResultRead:
    """Convert an AnalysisResult ORM object to AnalysisResultRead schema."""
    # Extract company info
    company_ticker = None
    company_name = None
    if hasattr(result, "company") and result.company:
        company_ticker = result.company.ticker
        company_name = result.company.name

    # Build criteria results from result_details JSONB
    criteria_results = []
    for detail in (result.result_details or []):
        # Convert string year keys back to int
        values_by_year: dict[int, float | None] = {}
        for k, v in (detail.get("values_by_year") or {}).items():
            with contextlib.suppress(ValueError, TypeError):
                values_by_year[int(k)] = v

        criteria_results.append(
            CriteriaResultItem(
                criteria_name=detail.get("criteria_name", ""),
                category=detail.get("category", ""),
                formula=detail.get("formula", ""),
                values_by_year=values_by_year,
                latest_value=detail.get("latest_value"),
                threshold=detail.get("threshold", ""),
                passed=detail.get("passed", False),
                weighted_score=detail.get("weighted_score", 0.0),
                trend=detail.get("trend"),
                note=detail.get("note"),
            ),
        )

    pct = float(result.pct_score) if result.pct_score else 0.0
    grade = compute_grade(pct)

    return AnalysisResultRead(
        id=result.id,
        company_id=result.company_id,
        company_ticker=company_ticker,
        company_name=company_name,
        profile_id=result.profile_id,
        profile_version=result.profile_version,
        run_at=result.run_at,
        overall_score=result.overall_score,
        max_score=result.max_score,
        pct_score=result.pct_score,
        grade=grade,
        criteria_count=result.criteria_count,
        passed_count=result.passed_count,
        failed_count=result.failed_count,
        criteria_results=criteria_results,
        summary=result.summary,
        created_at=result.created_at,
    )


def _build_comparison_response(comparison: dict) -> ComparisonResponse:
    """Build a ComparisonResponse from the service's compare_companies output."""
    from decimal import Decimal

    no_data_ids: set = comparison.get("no_data_ids", set())
    ranked_results = comparison["ranked_results"]

    rankings: list[CompanyComparisonItem] = []
    for rank_idx, r in enumerate(ranked_results, start=1):
        company_ticker = r.company.ticker if r.company else None
        company_name = r.company.name if r.company else None
        is_no_data = r.company_id in no_data_ids

        # Build per-criterion cells
        cells: list[CompanyCriterionCell] = []
        for detail in (r.result_details or []):
            values_by_year: dict[int, float | None] = {}
            for k, v in (detail.get("values_by_year") or {}).items():
                with contextlib.suppress(ValueError, TypeError):
                    values_by_year[int(k)] = v

            cells.append(
                CompanyCriterionCell(
                    criteria_name=detail.get("criteria_name", ""),
                    category=detail.get("category", ""),
                    formula=detail.get("formula", ""),
                    latest_value=detail.get("latest_value"),
                    threshold=detail.get("threshold", ""),
                    passed=detail.get("passed", False),
                    has_data=detail.get("has_data", True),
                    weighted_score=detail.get("weighted_score", 0.0),
                    weight=detail.get("weight", 0.0),
                    trend=detail.get("trend"),
                    values_by_year=values_by_year,
                ),
            )

        pct = float(r.pct_score) if r.pct_score else 0.0

        rankings.append(
            CompanyComparisonItem(
                rank=rank_idx,
                company_id=r.company_id,
                company_ticker=company_ticker,
                company_name=company_name,
                result_id=r.id,
                overall_score=r.overall_score or Decimal("0"),
                max_score=r.max_score or Decimal("0"),
                pct_score=r.pct_score or Decimal("0"),
                grade=compute_grade(pct),
                passed_count=r.passed_count or 0,
                failed_count=r.failed_count or 0,
                criteria_count=r.criteria_count or 0,
                status="no_data" if is_no_data else "scored",
                criteria_results=cells,
                summary=r.summary,
            ),
        )

    return ComparisonResponse(
        profile_id=comparison["profile_id"],
        profile_name=comparison["profile_name"],
        companies_count=comparison["companies_count"],
        criteria_names=comparison["criteria_names"],
        rankings=rankings,
    )
