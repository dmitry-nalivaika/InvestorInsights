# filepath: backend/app/analysis/engine.py
"""Analysis execution engine.

Orchestrates the full analysis pipeline:
  1. Load financial data for company across years.
  2. Resolve each criterion formula (built-in or custom).
  3. Compute formula values across all available years.
  4. Detect trends via OLS regression.
  5. Evaluate thresholds (pass/fail).
  6. Score and grade.

Task: T506
"""

from __future__ import annotations

from typing import Any

from app.analysis.expression_parser import (
    FormulaContext,
    parse_expression,
)
from app.analysis.formulas import resolve_expression
from app.analysis.scorer import (
    AnalysisScore,
    CriterionScore,
    compute_analysis_score,
    evaluate_threshold,
    format_threshold,
)
from app.analysis.trend import detect_trend
from app.observability.logging import get_logger

logger = get_logger(__name__)


def build_data_by_year(
    financial_statements: list[dict[str, Any]],
) -> dict[int, dict[str, dict[str, Any]]]:
    """Build a year-indexed lookup from financial statement records.

    Each FinancialStatement ORM object has:
      - fiscal_year: int
      - statement_data: dict with keys like ``income_statement``, ``balance_sheet``, ``cash_flow``

    Accepts either ORM objects (with .fiscal_year / .statement_data attributes)
    or plain dicts.
    """
    result: dict[int, dict[str, dict[str, Any]]] = {}

    for stmt in financial_statements:
        if isinstance(stmt, dict):
            year = stmt.get("fiscal_year")
            data = stmt.get("statement_data", {})
        else:
            year = getattr(stmt, "fiscal_year", None)
            data = getattr(stmt, "statement_data", {})

        if year is None or not data:
            continue

        # Merge: sometimes we might have annual + quarterly for same year
        # We prefer annual data (quarterly=None). Here we just take first seen.
        if year not in result:
            result[year] = {}

        for stmt_type in ("income_statement", "balance_sheet", "cash_flow"):
            # Don't overwrite if already present (annual takes precedence)
            if stmt_type in data and stmt_type not in result[year]:
                result[year][stmt_type] = data[stmt_type]

    return result


def _compute_values_by_year(
    expression: str,
    data_by_year: dict[int, dict[str, dict[str, Any]]],
    years: list[int],
) -> dict[int, float | None]:
    """Compute a formula expression for each year."""
    values: dict[int, float | None] = {}
    ast = parse_expression(expression)
    for year in years:
        ctx = FormulaContext(data_by_year, year)
        from app.analysis.expression_parser import evaluate
        values[year] = evaluate(ast, ctx)
    return values


def run_criterion(
    *,
    name: str,
    category: str,
    formula_name: str,
    is_custom_formula: bool,
    comparison: str,
    threshold_value: float | None,
    threshold_low: float | None,
    threshold_high: float | None,
    weight: float,
    lookback_years: int,
    data_by_year: dict[int, dict[str, dict[str, Any]]],
    latest_year: int,
) -> CriterionScore:
    """Evaluate a single analysis criterion.

    Args:
        name: Human-readable criterion name.
        category: Category string.
        formula_name: Built-in formula name or custom expression.
        is_custom_formula: Whether formula_name is a custom expression.
        comparison: Comparison operator string.
        threshold_value: Single threshold (for >, >=, <, <=, =).
        threshold_low: Low bound (for 'between').
        threshold_high: High bound (for 'between').
        weight: Score weight.
        lookback_years: How many years of data to consider.
        data_by_year: Year-indexed financial data.
        latest_year: Most recent fiscal year.

    Returns:
        CriterionScore with computed values, pass/fail, and trend.
    """
    # Resolve expression
    try:
        expression = resolve_expression(formula_name, is_custom=is_custom_formula)
    except ValueError as exc:
        logger.warning("Formula resolution failed for %s: %s", name, exc)
        return CriterionScore(
            name=name,
            category=category,
            formula=formula_name,
            values_by_year={},
            latest_value=None,
            threshold_display=format_threshold(
                comparison, threshold_value, threshold_low, threshold_high,
            ),
            passed=False,
            has_data=False,
            weighted_score=0.0,
            weight=weight,
            trend=None,
            note=f"Formula error: {exc}",
        )

    # Determine years to compute
    start_year = latest_year - lookback_years + 1
    all_years = sorted(yr for yr in data_by_year if start_year <= yr <= latest_year)

    if not all_years:
        return CriterionScore(
            name=name,
            category=category,
            formula=formula_name,
            values_by_year={},
            latest_value=None,
            threshold_display=format_threshold(
                comparison, threshold_value, threshold_low, threshold_high,
            ),
            passed=False,
            has_data=False,
            weighted_score=0.0,
            weight=weight,
            trend=None,
            note="No financial data available for lookback period",
        )

    # Compute values across years
    try:
        values_by_year = _compute_values_by_year(expression, data_by_year, all_years)
    except Exception as exc:
        logger.warning("Formula computation failed for %s: %s", name, exc)
        return CriterionScore(
            name=name,
            category=category,
            formula=formula_name,
            values_by_year={},
            latest_value=None,
            threshold_display=format_threshold(
                comparison, threshold_value, threshold_low, threshold_high,
            ),
            passed=False,
            has_data=False,
            weighted_score=0.0,
            weight=weight,
            trend=None,
            note=f"Computation error: {exc}",
        )

    latest_value = values_by_year.get(latest_year)

    # Detect trend
    trend_result = detect_trend(values_by_year)
    trend_str = (
        trend_result.direction
        if trend_result.direction != "insufficient_data"
        else None
    )

    # Evaluate threshold
    passed_result = evaluate_threshold(
        value=latest_value,
        comparison=comparison,
        threshold_value=threshold_value,
        threshold_low=threshold_low,
        threshold_high=threshold_high,
        trend_direction=trend_str,
    )

    has_data = passed_result is not None
    passed = passed_result is True

    # Build note
    note = None
    if not has_data:
        note = "Insufficient data to evaluate"
    elif trend_str:
        note = f"Trend: {trend_str}"

    return CriterionScore(
        name=name,
        category=category,
        formula=formula_name,
        values_by_year=values_by_year,
        latest_value=latest_value,
        threshold_display=format_threshold(
            comparison, threshold_value, threshold_low, threshold_high,
        ),
        passed=passed,
        has_data=has_data,
        weighted_score=weight if passed else 0.0,
        weight=weight,
        trend=trend_str,
        note=note,
    )


def run_analysis(
    *,
    criteria: list[dict[str, Any]],
    data_by_year: dict[int, dict[str, dict[str, Any]]],
) -> AnalysisScore:
    """Run a full analysis profile against a company's financial data.

    Args:
        criteria: List of criterion dicts with keys matching
            run_criterion kwargs (name, category, formula, etc.).
        data_by_year: Year-indexed financial data.

    Returns:
        AnalysisScore with overall score, grade, and per-criterion results.
    """
    if not data_by_year:
        return compute_analysis_score([])

    latest_year = max(data_by_year.keys())

    scores: list[CriterionScore] = []
    for crit in criteria:
        score = run_criterion(
            name=crit["name"],
            category=crit["category"],
            formula_name=crit["formula"],
            is_custom_formula=crit.get("is_custom_formula", False),
            comparison=crit["comparison"],
            threshold_value=crit.get("threshold_value"),
            threshold_low=crit.get("threshold_low"),
            threshold_high=crit.get("threshold_high"),
            weight=float(crit.get("weight", 1.0)),
            lookback_years=int(crit.get("lookback_years", 5)),
            data_by_year=data_by_year,
            latest_year=latest_year,
        )
        scores.append(score)

    return compute_analysis_score(scores)
