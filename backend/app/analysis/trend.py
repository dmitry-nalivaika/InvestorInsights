# filepath: backend/app/analysis/trend.py
"""Trend detection via OLS linear regression.

Implements simple ordinary-least-squares regression to determine
whether a metric is improving, declining, or stable over time.

Algorithm:
  1. Collect non-null values across years.
  2. Require minimum 3 data points.
  3. Compute OLS slope.
  4. Normalise: slope / abs(mean).
  5. Classify:
     - > +3%  → "improving"
     - < -3%  → "declining"
     - else   → "stable"

Task: T507
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TrendResult:
    """Result of trend analysis."""

    direction: str  # "improving", "declining", "stable", "insufficient_data"
    slope: float | None = None
    normalised_slope: float | None = None
    data_points: int = 0
    r_squared: float | None = None


# Threshold for normalised slope classification
_TREND_THRESHOLD = 0.03  # 3%
_MIN_DATA_POINTS = 3


def detect_trend(values_by_year: dict[int, float | None]) -> TrendResult:
    """Detect trend direction from yearly metric values.

    Args:
        values_by_year: Mapping of fiscal_year → computed metric value.
            None values are excluded.

    Returns:
        TrendResult with direction and statistics.
    """
    # Filter to non-null values and sort by year
    valid: list[tuple[int, float]] = sorted(
        ((yr, v) for yr, v in values_by_year.items() if v is not None),
    )

    if len(valid) < _MIN_DATA_POINTS:
        return TrendResult(
            direction="insufficient_data",
            data_points=len(valid),
        )

    years = [float(yr) for yr, _ in valid]
    values = [v for _, v in valid]
    n = len(years)

    # OLS: y = mx + b
    mean_x = sum(years) / n
    mean_y = sum(values) / n

    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(years, values))
    denominator = sum((x - mean_x) ** 2 for x in years)

    if denominator == 0:
        return TrendResult(
            direction="stable",
            slope=0.0,
            normalised_slope=0.0,
            data_points=n,
            r_squared=None,
        )

    slope = numerator / denominator
    intercept = mean_y - slope * mean_x

    # R² calculation
    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(years, values))
    ss_tot = sum((y - mean_y) ** 2 for y in values)
    r_squared = 1.0 - (ss_res / ss_tot) if ss_tot != 0 else None

    # Normalised slope = OLS slope / abs(mean_y)
    abs_mean = abs(mean_y)
    if abs_mean == 0:
        normalised = 0.0
    else:
        normalised = slope / abs_mean

    # Classify
    if normalised > _TREND_THRESHOLD:
        direction = "improving"
    elif normalised < -_TREND_THRESHOLD:
        direction = "declining"
    else:
        direction = "stable"

    return TrendResult(
        direction=direction,
        slope=round(slope, 8),
        normalised_slope=round(normalised, 6),
        data_points=n,
        r_squared=round(r_squared, 6) if r_squared is not None else None,
    )
