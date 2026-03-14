# filepath: backend/app/xbrl/mapper.py
"""XBRL companyfacts → internal financial data mapper.

Transforms the raw SEC EDGAR companyfacts JSON into structured
financial statements keyed by (fiscal_year, fiscal_quarter).
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.observability.logging import get_logger
from app.xbrl.tag_registry import (
    ALL_MAPPINGS,
    TagMapping,
)

logger = get_logger(__name__)

# Period duration thresholds (from xbrl-tag-mapping.md)
_ANNUAL_MIN_DAYS = 335
_ANNUAL_MAX_DAYS = 395
_QUARTERLY_MIN_DAYS = 75
_QUARTERLY_MAX_DAYS = 105


def map_company_facts(
    raw_facts: dict[str, Any],
    *,
    start_year: int | None = None,
    end_year: int | None = None,
) -> list[dict[str, Any]]:
    """Transform raw SEC companyfacts JSON into structured financial periods.

    Args:
        raw_facts: Raw JSON from SEC /api/xbrl/companyfacts/CIK{cik}.json.
        start_year: Only include periods from this year.
        end_year: Only include periods up to this year.

    Returns:
        List of dicts, each representing a financial period:
        {
            "fiscal_year": int,
            "fiscal_quarter": int | None,
            "period_end_date": str (ISO date),
            "income_statement": {...},
            "balance_sheet": {...},
            "cash_flow": {...},
        }
    """
    us_gaap = raw_facts.get("facts", {}).get("us-gaap", {})
    if not us_gaap:
        logger.warning("No us-gaap facts found in companyfacts response")
        return []

    # Collect all values per (period_end, period_type) → internal_field → value
    # period_key = (period_end_date, "annual"|"quarterly")
    period_data: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}

    for mapping in ALL_MAPPINGS:
        _extract_mapping_values(us_gaap, mapping, period_data)

    # Build structured financial periods
    results: list[dict[str, Any]] = []
    for (period_end, period_type), statements in sorted(period_data.items()):
        try:
            end_date = date.fromisoformat(period_end)
        except ValueError:
            continue

        fiscal_year = end_date.year
        fiscal_quarter = None
        if period_type == "quarterly":
            fiscal_quarter = (end_date.month - 1) // 3 + 1
            # Adjust: if Q4 and fiscal year doesn't match
            if fiscal_quarter == 0:
                fiscal_quarter = 4

        # Apply year filters
        if start_year and fiscal_year < start_year:
            continue
        if end_year and fiscal_year > end_year:
            continue

        income_statement = statements.get("income_statement", {})
        balance_sheet = statements.get("balance_sheet", {})
        cash_flow = statements.get("cash_flow", {})

        # Apply fallback formulas
        _apply_fallbacks(income_statement, balance_sheet, cash_flow)

        # Only include if we have at least some data
        if not income_statement and not balance_sheet and not cash_flow:
            continue

        results.append({
            "fiscal_year": fiscal_year,
            "fiscal_quarter": fiscal_quarter,
            "period_end_date": period_end,
            "income_statement": income_statement,
            "balance_sheet": balance_sheet,
            "cash_flow": cash_flow,
        })

    logger.info(
        "XBRL facts mapped",
        periods_found=len(results),
        annual=sum(1 for r in results if r["fiscal_quarter"] is None),
        quarterly=sum(1 for r in results if r["fiscal_quarter"] is not None),
    )

    return results


def _extract_mapping_values(
    us_gaap: dict[str, Any],
    mapping: TagMapping,
    period_data: dict[tuple[str, str], dict[str, dict[str, Any]]],
) -> None:
    """Extract values for a single mapping from the us-gaap facts."""
    for xbrl_tag in mapping.xbrl_tags:
        tag_data = us_gaap.get(xbrl_tag)
        if not tag_data:
            continue

        units = tag_data.get("units", {})
        # Try USD first, then shares, then pure
        values_list = units.get("USD") or units.get("shares") or units.get("USD/shares") or units.get("pure", [])

        if not values_list:
            continue

        for fact in values_list:
            val = fact.get("val")
            if val is None:
                continue

            end_date = fact.get("end", "")
            start_date = fact.get("start")

            if not end_date:
                continue

            # Determine period type
            if mapping.period_type == "instant":
                # For instant (balance sheet), classify by whether this looks
                # like a year-end or quarter-end
                period_type = _classify_instant_period(end_date)
            elif mapping.period_type == "duration" and start_date:
                period_type = _classify_duration_period(start_date, end_date)
            else:
                continue

            if period_type is None:
                continue

            # Apply negation if needed
            numeric_val = float(val)
            if mapping.negate:
                numeric_val = -abs(numeric_val)

            period_key = (end_date, period_type)
            if period_key not in period_data:
                period_data[period_key] = {}
            if mapping.statement not in period_data[period_key]:
                period_data[period_key][mapping.statement] = {}

            # Only set if not already set (first matching tag wins)
            if mapping.internal_field not in period_data[period_key][mapping.statement]:
                period_data[period_key][mapping.statement][mapping.internal_field] = numeric_val

        # If we found values for this tag, don't try lower-priority tags
        break


def _classify_duration_period(start_date: str, end_date: str) -> str | None:
    """Classify a duration fact as annual or quarterly."""
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
        days = (end - start).days
    except ValueError:
        return None

    if _ANNUAL_MIN_DAYS <= days <= _ANNUAL_MAX_DAYS:
        return "annual"
    elif _QUARTERLY_MIN_DAYS <= days <= _QUARTERLY_MAX_DAYS:
        return "quarterly"
    return None


def _classify_instant_period(end_date: str) -> str | None:
    """Classify an instant fact — always treat as annual (year-end snapshot)."""
    # For balance sheet items, we include both annual and quarterly snapshots.
    # We can't distinguish from just the date, so we default to "annual"
    # for fiscal year-end dates and "quarterly" for others.
    # In practice, many companies report quarterly balance sheets too.
    try:
        d = date.fromisoformat(end_date)
        # Common fiscal year ends: March, June, September, December
        if d.month in (3, 6, 9, 12) and d.day >= 28:
            # Could be year-end or quarter-end
            # We'll include as annual; quarterly data handled by duration filtering
            return "annual"
        return "quarterly"
    except ValueError:
        return None


def _apply_fallbacks(
    income_statement: dict[str, Any],
    balance_sheet: dict[str, Any],
    cash_flow: dict[str, Any],
) -> None:
    """Apply computed fallback fields."""
    # gross_profit = revenue - cost_of_revenue
    if "gross_profit" not in income_statement:
        rev = income_statement.get("revenue")
        cogs = income_statement.get("cost_of_revenue")
        if rev is not None and cogs is not None:
            income_statement["gross_profit"] = rev - cogs

    # free_cash_flow = operating_cash_flow + capital_expenditure
    if "free_cash_flow" not in cash_flow:
        ocf = cash_flow.get("operating_cash_flow")
        capex = cash_flow.get("capital_expenditure")
        if ocf is not None and capex is not None:
            cash_flow["free_cash_flow"] = ocf + capex
