# filepath: backend/app/xbrl/period_selector.py
"""XBRL period selector — disambiguate multiple values for the same period.

When SEC filings contain multiple values for the same fact+period
(e.g. original filing vs amendment), this module picks the best one.
"""

from __future__ import annotations

from datetime import date
from typing import Any


def select_best_value(
    facts: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Select the best fact from a list of candidates for the same period.

    Priority (from xbrl-tag-mapping.md):
        1. Same fiscal period, latest filing date
        2. Prefer original over amendments (10-K over 10-K/A)

    Args:
        facts: List of fact dicts from companyfacts API.

    Returns:
        The best fact dict, or None if the list is empty.
    """
    if not facts:
        return None

    if len(facts) == 1:
        return facts[0]

    # Sort by priority
    def _sort_key(fact: dict[str, Any]) -> tuple:
        form = fact.get("form", "")
        filed = fact.get("filed", "")

        # Prefer non-amendment filings
        is_amendment = 1 if "/A" in form else 0

        # Prefer later filing date
        try:
            filed_date = date.fromisoformat(filed)
            filed_ordinal = filed_date.toordinal()
        except (ValueError, TypeError):
            filed_ordinal = 0

        return (is_amendment, -filed_ordinal)

    sorted_facts = sorted(facts, key=_sort_key)
    return sorted_facts[0]
