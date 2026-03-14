# filepath: backend/app/services/analysis_service.py
"""Analysis service — business logic for profiles, execution, and results.

Tasks: T504 (profile CRUD), T505 (criteria management), T506 (execution),
       T510 (persistence), T511 (AI summary), T514 (default profile seeding)
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from app.analysis.engine import build_data_by_year, run_analysis
from app.analysis.expression_parser import validate_expression
from app.analysis.formulas import FORMULA_REGISTRY, resolve_expression
from app.analysis.scorer import compute_grade
from app.api.middleware.error_handler import ConflictError, NotFoundError, ValidationError
from app.db.repositories.financial_repo import FinancialRepository
from app.db.repositories.profile_repo import ProfileRepository
from app.db.repositories.result_repo import ResultRepository
from app.observability.logging import get_logger

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.clients.openai_client import AzureOpenAIClient
    from app.models.profile import AnalysisProfile
    from app.models.result import AnalysisResult

logger = get_logger(__name__)


class AnalysisService:
    """Business logic for analysis profiles, execution, and results."""

    def __init__(
        self,
        session: AsyncSession,
        openai_client: AzureOpenAIClient | None = None,
    ) -> None:
        self._session = session
        self._profile_repo = ProfileRepository(session)
        self._result_repo = ResultRepository(session)
        self._financial_repo = FinancialRepository(session)
        self._openai = openai_client

    # ── Profile CRUD (T504-T505) ─────────────────────────────────

    async def create_profile(
        self,
        *,
        name: str,
        description: str | None = None,
        is_default: bool = False,
        criteria: list[dict[str, Any]],
    ) -> AnalysisProfile:
        """Create an analysis profile with criteria.

        Raises:
            ConflictError: If profile name already exists.
            ValidationError: If any formula is invalid.
        """
        existing = await self._profile_repo.get_by_name(name)
        if existing:
            raise ConflictError(f"Profile name {name!r} already exists")

        # Validate all formulas
        self._validate_criteria(criteria)

        # If setting as default, unset any existing default
        if is_default:
            await self._unset_defaults()

        profile = await self._profile_repo.create(
            name=name,
            description=description,
            is_default=is_default,
            criteria=self._prepare_criteria_dicts(criteria),
        )
        return profile

    async def get_profile(self, profile_id: uuid.UUID) -> AnalysisProfile:
        """Get a profile by ID. Raises NotFoundError."""
        profile = await self._profile_repo.get_by_id(profile_id)
        if not profile:
            raise NotFoundError(f"Profile {profile_id} not found")
        return profile

    async def list_profiles(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AnalysisProfile], int]:
        """List profiles with pagination."""
        return await self._profile_repo.list_all(limit=limit, offset=offset)

    async def update_profile(
        self,
        profile_id: uuid.UUID,
        *,
        name: str | None = None,
        description: str | None = None,
        is_default: bool | None = None,
        criteria: list[dict[str, Any]] | None = None,
    ) -> AnalysisProfile:
        """Update a profile. Increments version when criteria change.

        Raises:
            NotFoundError: If profile doesn't exist.
            ConflictError: If new name conflicts.
            ValidationError: If any formula is invalid.
        """
        profile = await self._profile_repo.get_by_id(profile_id)
        if not profile:
            raise NotFoundError(f"Profile {profile_id} not found")

        # Check name uniqueness
        if name and name != profile.name:
            existing = await self._profile_repo.get_by_name(name)
            if existing:
                raise ConflictError(f"Profile name {name!r} already exists")

        # Validate criteria if provided
        new_criteria_dicts = None
        if criteria is not None:
            self._validate_criteria(criteria)
            new_criteria_dicts = self._prepare_criteria_dicts(criteria)

        if is_default is True:
            await self._unset_defaults()

        updates: dict[str, Any] = {}
        if name is not None:
            updates["name"] = name
        if description is not None:
            updates["description"] = description
        if is_default is not None:
            updates["is_default"] = is_default

        return await self._profile_repo.update(
            profile,
            updates=updates,
            new_criteria=new_criteria_dicts,
        )

    async def delete_profile(self, profile_id: uuid.UUID) -> None:
        """Delete a profile. Raises NotFoundError."""
        profile = await self._profile_repo.get_by_id(profile_id)
        if not profile:
            raise NotFoundError(f"Profile {profile_id} not found")
        await self._profile_repo.delete(profile)

    # ── Analysis execution (T506, T509-T511) ─────────────────────

    async def run_analysis(
        self,
        *,
        company_ids: list[uuid.UUID],
        profile_id: uuid.UUID,
        generate_summary: bool = True,
    ) -> list[AnalysisResult]:
        """Execute an analysis profile against one or more companies.

        Args:
            company_ids: 1-10 company UUIDs to analyse.
            profile_id: The profile to run.
            generate_summary: Whether to generate an AI narrative summary.

        Returns:
            List of AnalysisResult ORM objects (one per company).

        Raises:
            NotFoundError: If profile or any company not found.
        """
        from app.models.company import Company

        profile = await self._profile_repo.get_by_id(profile_id)
        if not profile:
            raise NotFoundError(f"Profile {profile_id} not found")

        # Load companies
        from sqlalchemy import select
        stmt = select(Company).where(Company.id.in_(company_ids))
        result = await self._session.execute(stmt)
        companies = {c.id: c for c in result.scalars().all()}

        missing = set(company_ids) - set(companies.keys())
        if missing:
            raise NotFoundError(f"Companies not found: {missing}")

        # Build criteria list from profile
        criteria_dicts = [
            {
                "name": c.name,
                "category": c.category.value if hasattr(c.category, "value") else str(c.category),
                "formula": c.formula,
                "is_custom_formula": c.is_custom_formula,
                "comparison": c.comparison.value if hasattr(c.comparison, "value") else str(c.comparison),
                "threshold_value": float(c.threshold_value) if c.threshold_value is not None else None,
                "threshold_low": float(c.threshold_low) if c.threshold_low is not None else None,
                "threshold_high": float(c.threshold_high) if c.threshold_high is not None else None,
                "weight": float(c.weight),
                "lookback_years": c.lookback_years,
            }
            for c in profile.criteria
            if c.enabled
        ]

        results: list[AnalysisResult] = []

        for company_id in company_ids:
            company = companies[company_id]

            # Load financial data (annual only)
            financials, _ = await self._financial_repo.list_by_company(
                company_id,
                period_type="annual",
                sort_order="asc",
                limit=100,
                offset=0,
            )

            data_by_year = build_data_by_year(financials)

            if not data_by_year:
                logger.warning(
                    "No financial data for company %s (%s)",
                    company.ticker,
                    company_id,
                )

            # Run analysis engine
            score = run_analysis(
                criteria=criteria_dicts,
                data_by_year=data_by_year,
            )

            # Build result_details JSONB
            result_details = [
                {
                    "criteria_name": cs.name,
                    "category": cs.category,
                    "formula": cs.formula,
                    "values_by_year": {
                        str(yr): round(v, 6) if v is not None else None
                        for yr, v in cs.values_by_year.items()
                    },
                    "latest_value": round(cs.latest_value, 6) if cs.latest_value is not None else None,
                    "threshold": cs.threshold_display,
                    "passed": cs.passed,
                    "has_data": cs.has_data,
                    "weighted_score": round(cs.weighted_score, 4),
                    "weight": round(cs.weight, 4),
                    "trend": cs.trend,
                    "note": cs.note,
                }
                for cs in score.criteria_scores
            ]

            # Generate AI summary (T511)
            summary = None
            if generate_summary and data_by_year:
                summary = await self._generate_summary(
                    company_name=company.name,
                    company_ticker=company.ticker,
                    score=score,
                    profile_name=profile.name,
                )

            # Persist result (T510 — single transaction)
            analysis_result = await self._result_repo.create(
                company_id=company_id,
                profile_id=profile.id,
                profile_version=profile.version,
                run_at=datetime.now(timezone.utc),
                overall_score=score.overall_score,
                max_score=score.max_score,
                pct_score=score.pct_score,
                criteria_count=score.criteria_count,
                passed_count=score.passed_count,
                failed_count=score.failed_count,
                result_details=result_details,
                summary=summary,
            )

            # Attach company info for response building
            analysis_result.company = company
            analysis_result.profile = profile

            results.append(analysis_result)

        return results

    # ── Results retrieval (T512) ─────────────────────────────────

    async def get_result(self, result_id: uuid.UUID) -> AnalysisResult:
        """Get an analysis result by ID. Raises NotFoundError."""
        result = await self._result_repo.get_by_id(result_id)
        if not result:
            raise NotFoundError(f"Analysis result {result_id} not found")
        return result

    async def list_results(
        self,
        *,
        company_id: uuid.UUID | None = None,
        profile_id: uuid.UUID | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[AnalysisResult], int]:
        """List analysis results with optional filters."""
        return await self._result_repo.list_results(
            company_id=company_id,
            profile_id=profile_id,
            limit=limit,
            offset=offset,
        )

    # ── Default profile seeding (T514) ───────────────────────────

    async def seed_default_profile(self) -> AnalysisProfile | None:
        """Seed the default 'Quality Value Investor' profile if it doesn't exist.

        Returns the profile if created, None if already exists.
        """
        existing = await self._profile_repo.get_by_name("Quality Value Investor")
        if existing:
            logger.info("Default profile already exists, skipping seed")
            return None

        from app.models.criterion import CriteriaCategory, ComparisonOp

        criteria = [
            # Profitability (5)
            {"name": "Gross Margin > 40%", "category": CriteriaCategory.PROFITABILITY, "formula": "gross_margin", "comparison": ComparisonOp.GTE, "threshold_value": Decimal("0.40"), "weight": Decimal("2.0"), "lookback_years": 5},
            {"name": "Operating Margin > 15%", "category": CriteriaCategory.PROFITABILITY, "formula": "operating_margin", "comparison": ComparisonOp.GTE, "threshold_value": Decimal("0.15"), "weight": Decimal("2.0"), "lookback_years": 5},
            {"name": "Net Margin > 10%", "category": CriteriaCategory.PROFITABILITY, "formula": "net_margin", "comparison": ComparisonOp.GTE, "threshold_value": Decimal("0.10"), "weight": Decimal("1.5"), "lookback_years": 5},
            {"name": "ROE > 15%", "category": CriteriaCategory.PROFITABILITY, "formula": "roe", "comparison": ComparisonOp.GTE, "threshold_value": Decimal("0.15"), "weight": Decimal("2.5"), "lookback_years": 5},
            {"name": "ROIC > 12%", "category": CriteriaCategory.PROFITABILITY, "formula": "roic", "comparison": ComparisonOp.GTE, "threshold_value": Decimal("0.12"), "weight": Decimal("3.0"), "lookback_years": 5},
            # Growth (3)
            {"name": "Revenue Growth > 5%", "category": CriteriaCategory.GROWTH, "formula": "revenue_growth", "comparison": ComparisonOp.GTE, "threshold_value": Decimal("0.05"), "weight": Decimal("1.5"), "lookback_years": 5},
            {"name": "Earnings Growth Positive", "category": CriteriaCategory.GROWTH, "formula": "earnings_growth", "comparison": ComparisonOp.GT, "threshold_value": Decimal("0.0"), "weight": Decimal("1.0"), "lookback_years": 5},
            {"name": "Revenue Trend Improving", "category": CriteriaCategory.GROWTH, "formula": "revenue_growth", "comparison": ComparisonOp.TREND_UP, "weight": Decimal("1.0"), "lookback_years": 5},
            # Solvency (2)
            {"name": "Debt-to-Equity < 1.0", "category": CriteriaCategory.SOLVENCY, "formula": "debt_to_equity", "comparison": ComparisonOp.LTE, "threshold_value": Decimal("1.0"), "weight": Decimal("2.0"), "lookback_years": 5},
            {"name": "Interest Coverage > 5x", "category": CriteriaCategory.SOLVENCY, "formula": "interest_coverage", "comparison": ComparisonOp.GTE, "threshold_value": Decimal("5.0"), "weight": Decimal("1.5"), "lookback_years": 5},
            # Liquidity (1)
            {"name": "Current Ratio > 1.2", "category": CriteriaCategory.LIQUIDITY, "formula": "current_ratio", "comparison": ComparisonOp.GTE, "threshold_value": Decimal("1.2"), "weight": Decimal("1.0"), "lookback_years": 3},
            # Cash Flow Quality (4)
            {"name": "FCF Margin > 10%", "category": CriteriaCategory.QUALITY, "formula": "fcf_margin", "comparison": ComparisonOp.GTE, "threshold_value": Decimal("0.10"), "weight": Decimal("2.5"), "lookback_years": 5},
            {"name": "OCF > Net Income", "category": CriteriaCategory.QUALITY, "formula": "operating_cash_flow_ratio", "comparison": ComparisonOp.GTE, "threshold_value": Decimal("1.0"), "weight": Decimal("2.0"), "lookback_years": 5},
            {"name": "FCF Conversion > 80%", "category": CriteriaCategory.QUALITY, "formula": "fcf_to_net_income", "comparison": ComparisonOp.GTE, "threshold_value": Decimal("0.80"), "weight": Decimal("1.5"), "lookback_years": 5},
            {"name": "SBC < 5% of Revenue", "category": CriteriaCategory.QUALITY, "formula": "sbc_to_revenue", "comparison": ComparisonOp.LTE, "threshold_value": Decimal("0.05"), "weight": Decimal("1.0"), "lookback_years": 3},
        ]

        profile = await self._profile_repo.create(
            name="Quality Value Investor",
            description=(
                "A balanced analysis profile for quality-focused value investors. "
                "Evaluates profitability, capital efficiency, financial health, "
                "growth, and cash flow quality. Suitable for established companies "
                "with 5+ years of financial history."
            ),
            is_default=True,
            criteria=criteria,
        )

        logger.info("Seeded default analysis profile: %s", profile.name)
        return profile

    # ── Private helpers ──────────────────────────────────────────

    def _validate_criteria(self, criteria: list[dict[str, Any]]) -> None:
        """Validate all criteria formulas. Raises ValidationError on failure."""
        errors: list[str] = []
        for i, crit in enumerate(criteria):
            formula = crit.get("formula", "")
            is_custom = crit.get("is_custom_formula", False)

            if is_custom:
                errs = validate_expression(formula)
                if errs:
                    errors.append(
                        f"Criterion #{i + 1} ({crit.get('name', '?')}): {'; '.join(errs)}",
                    )
            else:
                # Must be a known built-in formula
                if formula not in FORMULA_REGISTRY:
                    errors.append(
                        f"Criterion #{i + 1} ({crit.get('name', '?')}): "
                        f"Unknown built-in formula {formula!r}",
                    )

        if errors:
            raise ValidationError("; ".join(errors))

    def _prepare_criteria_dicts(
        self,
        criteria: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Convert schema dicts to ORM-ready dicts."""
        result: list[dict[str, Any]] = []
        for i, crit in enumerate(criteria):
            d = dict(crit)
            if "sort_order" not in d:
                d["sort_order"] = i
            result.append(d)
        return result

    async def _unset_defaults(self) -> None:
        """Unset is_default on all profiles."""
        from sqlalchemy import update
        from app.models.profile import AnalysisProfile

        stmt = (
            update(AnalysisProfile)
            .where(AnalysisProfile.is_default.is_(True))
            .values(is_default=False)
        )
        await self._session.execute(stmt)

    async def _generate_summary(
        self,
        *,
        company_name: str,
        company_ticker: str,
        score: Any,
        profile_name: str,
    ) -> str | None:
        """Generate AI narrative summary via LLM (T511).

        Returns None if LLM is unavailable (NFR-401 graceful degradation).
        """
        if self._openai is None:
            logger.info("No OpenAI client available, skipping AI summary")
            return None

        # Build summary prompt
        strengths = []
        concerns = []
        data_gaps = []

        for cs in score.criteria_scores:
            if not cs.has_data:
                data_gaps.append(cs.name)
            elif cs.passed:
                val_str = f" ({cs.latest_value:.4f})" if cs.latest_value is not None else ""
                trend_str = f", trend: {cs.trend}" if cs.trend else ""
                strengths.append(f"{cs.name}{val_str}{trend_str}")
            else:
                val_str = f" ({cs.latest_value:.4f})" if cs.latest_value is not None else ""
                trend_str = f", trend: {cs.trend}" if cs.trend else ""
                concerns.append(f"{cs.name}: {cs.threshold_display}{val_str}{trend_str}")

        prompt = (
            f"You are a financial analyst. Provide a concise 2-3 paragraph summary "
            f"of the analysis results for {company_name} ({company_ticker}) "
            f"using the '{profile_name}' analysis profile.\n\n"
            f"Overall: {score.pct_score}% ({score.grade} grade), "
            f"{score.passed_count} passed / {score.failed_count} failed "
            f"out of {score.criteria_count} criteria.\n\n"
        )

        if strengths:
            prompt += f"Strengths:\n" + "\n".join(f"  ✓ {s}" for s in strengths) + "\n\n"
        if concerns:
            prompt += f"Concerns:\n" + "\n".join(f"  ✗ {c}" for c in concerns) + "\n\n"
        if data_gaps:
            prompt += f"Data gaps (not evaluated):\n" + "\n".join(f"  ? {d}" for d in data_gaps) + "\n\n"

        prompt += (
            "Write a professional summary covering strengths, concerns, and any data gaps. "
            "Be specific about the numbers. Keep it under 200 words."
        )

        try:
            response = await self._openai.chat_completion(
                messages=[
                    {"role": "system", "content": "You are a financial analysis assistant."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=500,
            )
            return response.content.strip() if response.content else None
        except Exception:
            logger.warning(
                "AI summary generation failed for %s, returning null",
                company_ticker,
                exc_info=True,
            )
            return None
