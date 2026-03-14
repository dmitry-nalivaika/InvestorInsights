# filepath: backend/app/analysis/scorer.py
"""Analysis scoring — binary pass/fail × weight with grade assignment.

Scoring rules (from plan.md):
  - Each criterion is evaluated as pass (1) or fail (0).
  - Score contribution = pass × weight.
  - ``no_data`` criteria are excluded from max possible score.
  - Grade thresholds:
      A: 90-100%, B: 75-89%, C: 60-74%, D: 40-59%, F: 0-39%

Task: T508
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass
class CriterionScore:
    """Scoring result for a single criterion."""

    name: str
    category: str
    formula: str
    values_by_year: dict[int, float | None]
    latest_value: float | None
    threshold_display: str  # human-readable, e.g. ">= 0.15"
    passed: bool
    has_data: bool
    weighted_score: float  # weight if passed, 0 if failed
    weight: float
    trend: str | None  # "improving" / "declining" / "stable" / None
    note: str | None


@dataclass
class AnalysisScore:
    """Aggregate scoring result for a company analysis."""

    overall_score: Decimal
    max_score: Decimal
    pct_score: Decimal
    grade: str
    criteria_count: int
    passed_count: int
    failed_count: int
    no_data_count: int
    criteria_scores: list[CriterionScore]


# ── Grade thresholds ─────────────────────────────────────────────

_GRADE_THRESHOLDS: list[tuple[float, str]] = [
    (90.0, "A"),
    (75.0, "B"),
    (60.0, "C"),
    (40.0, "D"),
    (0.0, "F"),
]


def compute_grade(pct: float) -> str:
    """Map a percentage score (0-100) to a letter grade."""
    for threshold, grade in _GRADE_THRESHOLDS:
        if pct >= threshold:
            return grade
    return "F"


# ── Threshold evaluation ─────────────────────────────────────────


def evaluate_threshold(
    value: float | None,
    comparison: str,
    threshold_value: float | None = None,
    threshold_low: float | None = None,
    threshold_high: float | None = None,
    trend_direction: str | None = None,
) -> bool | None:
    """Evaluate whether a value passes a threshold comparison.

    Returns:
        True if passes, False if fails, None if data is missing.
    """
    if comparison == "trend_up":
        if trend_direction is None:
            return None
        return trend_direction == "improving"

    if comparison == "trend_down":
        if trend_direction is None:
            return None
        return trend_direction == "declining"

    if value is None:
        return None

    if comparison == "between":
        if threshold_low is None or threshold_high is None:
            return None
        return threshold_low <= value <= threshold_high

    if threshold_value is None:
        return None

    if comparison == ">":
        return value > threshold_value
    if comparison == ">=":
        return value >= threshold_value
    if comparison == "<":
        return value < threshold_value
    if comparison == "<=":
        return value <= threshold_value
    if comparison == "=":
        return abs(value - threshold_value) < 1e-9

    return None  # Unknown comparison


def format_threshold(
    comparison: str,
    threshold_value: float | None = None,
    threshold_low: float | None = None,
    threshold_high: float | None = None,
) -> str:
    """Format a threshold into a human-readable string."""
    if comparison == "between" and threshold_low is not None and threshold_high is not None:
        return f"between {threshold_low} and {threshold_high}"
    if comparison in ("trend_up", "trend_down"):
        return comparison.replace("_", " ")
    if threshold_value is not None:
        return f"{comparison} {threshold_value}"
    return comparison


# ── Aggregate scorer ─────────────────────────────────────────────


def compute_analysis_score(criteria_scores: list[CriterionScore]) -> AnalysisScore:
    """Compute aggregate scores from individual criterion results.

    No-data criteria (has_data=False) are excluded from max_score,
    so they don't penalise the overall percentage.
    """
    overall = 0.0
    max_possible = 0.0
    passed_count = 0
    failed_count = 0
    no_data_count = 0

    for cs in criteria_scores:
        if not cs.has_data:
            no_data_count += 1
            continue
        max_possible += cs.weight
        if cs.passed:
            overall += cs.weight
            passed_count += 1
        else:
            failed_count += 1

    pct = (overall / max_possible * 100) if max_possible > 0 else 0.0
    grade = compute_grade(pct)

    return AnalysisScore(
        overall_score=Decimal(str(round(overall, 4))),
        max_score=Decimal(str(round(max_possible, 4))),
        pct_score=Decimal(str(round(pct, 2))),
        grade=grade,
        criteria_count=len(criteria_scores),
        passed_count=passed_count,
        failed_count=failed_count,
        no_data_count=no_data_count,
        criteria_scores=criteria_scores,
    )
