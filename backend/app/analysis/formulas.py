# filepath: backend/app/analysis/formulas.py
"""Built-in financial formula registry.

Contains 25+ formulas across profitability, growth, liquidity,
solvency, efficiency, cash flow quality, dividend, and composite
categories.  Each formula is a named expression that can be
evaluated against a company's financial statement_data JSONB.

References:
  - reference/builtin-formulas.md
  - plan.md § Analysis Engine
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BuiltinFormula:
    """Definition of a built-in financial formula."""

    name: str
    category: str
    expression: str
    description: str
    required_fields: list[str] = field(default_factory=list)
    example: str | None = None


# ── Profitability ────────────────────────────────────────────────

_PROFITABILITY: list[BuiltinFormula] = [
    BuiltinFormula(
        name="gross_margin",
        category="profitability",
        expression="income_statement.gross_profit / income_statement.revenue",
        description="Gross profit as a percentage of revenue. Measures pricing power and production efficiency.",
        required_fields=["income_statement.gross_profit", "income_statement.revenue"],
        example=">= 0.40 (40%)",
    ),
    BuiltinFormula(
        name="operating_margin",
        category="profitability",
        expression="income_statement.operating_income / income_statement.revenue",
        description="Operating income as a percentage of revenue. Measures core operational efficiency.",
        required_fields=["income_statement.operating_income", "income_statement.revenue"],
        example=">= 0.15 (15%)",
    ),
    BuiltinFormula(
        name="net_margin",
        category="profitability",
        expression="income_statement.net_income / income_statement.revenue",
        description="Net income as a percentage of revenue. Measures bottom-line profitability.",
        required_fields=["income_statement.net_income", "income_statement.revenue"],
        example=">= 0.10 (10%)",
    ),
    BuiltinFormula(
        name="roe",
        category="profitability",
        expression="income_statement.net_income / balance_sheet.total_equity",
        description="Return on equity. Measures profitability relative to shareholder equity.",
        required_fields=["income_statement.net_income", "balance_sheet.total_equity"],
        example=">= 0.15 (15%)",
    ),
    BuiltinFormula(
        name="roa",
        category="profitability",
        expression="income_statement.net_income / balance_sheet.total_assets",
        description="Return on assets. Measures how efficiently assets generate profit.",
        required_fields=["income_statement.net_income", "balance_sheet.total_assets"],
        example=">= 0.05 (5%)",
    ),
    BuiltinFormula(
        name="roic",
        category="profitability",
        expression=(
            "(income_statement.operating_income * (1 - 0.21)) / "
            "(balance_sheet.total_assets - balance_sheet.total_current_liabilities"
            " - balance_sheet.cash_and_equivalents)"
        ),
        description=(
            "Return on invested capital. Uses 21% statutory tax rate approximation. "
            "Measures value creation above cost of capital."
        ),
        required_fields=[
            "income_statement.operating_income",
            "balance_sheet.total_assets",
            "balance_sheet.total_current_liabilities",
            "balance_sheet.cash_and_equivalents",
        ],
        example=">= 0.12 (12%)",
    ),
]

# ── Growth ───────────────────────────────────────────────────────

_GROWTH: list[BuiltinFormula] = [
    BuiltinFormula(
        name="revenue_growth",
        category="growth",
        expression=(
            "(income_statement.revenue - prev(income_statement.revenue))"
            " / prev(income_statement.revenue)"
        ),
        description="Year-over-year revenue growth rate.",
        required_fields=["income_statement.revenue"],
        example=">= 0.05 (5%)",
    ),
    BuiltinFormula(
        name="earnings_growth",
        category="growth",
        expression=(
            "(income_statement.net_income - prev(income_statement.net_income))"
            " / abs(prev(income_statement.net_income))"
        ),
        description="Year-over-year net income growth rate.",
        required_fields=["income_statement.net_income"],
        example="> 0.0",
    ),
    BuiltinFormula(
        name="operating_income_growth",
        category="growth",
        expression=(
            "(income_statement.operating_income - prev(income_statement.operating_income))"
            " / abs(prev(income_statement.operating_income))"
        ),
        description="Year-over-year operating income growth rate.",
        required_fields=["income_statement.operating_income"],
        example="> 0.0",
    ),
    BuiltinFormula(
        name="fcf_growth",
        category="growth",
        expression=(
            "(cash_flow.free_cash_flow - prev(cash_flow.free_cash_flow))"
            " / abs(prev(cash_flow.free_cash_flow))"
        ),
        description="Year-over-year free cash flow growth rate.",
        required_fields=["cash_flow.free_cash_flow"],
        example="> 0.0",
    ),
]

# ── Liquidity ────────────────────────────────────────────────────

_LIQUIDITY: list[BuiltinFormula] = [
    BuiltinFormula(
        name="current_ratio",
        category="liquidity",
        expression="balance_sheet.total_current_assets / balance_sheet.total_current_liabilities",
        description="Current assets divided by current liabilities. Measures short-term liquidity.",
        required_fields=[
            "balance_sheet.total_current_assets",
            "balance_sheet.total_current_liabilities",
        ],
        example=">= 1.2",
    ),
    BuiltinFormula(
        name="quick_ratio",
        category="liquidity",
        expression=(
            "(balance_sheet.total_current_assets - balance_sheet.inventory)"
            " / balance_sheet.total_current_liabilities"
        ),
        description="Liquid assets divided by current liabilities, excluding inventory.",
        required_fields=[
            "balance_sheet.total_current_assets",
            "balance_sheet.inventory",
            "balance_sheet.total_current_liabilities",
        ],
        example=">= 1.0",
    ),
    BuiltinFormula(
        name="cash_ratio",
        category="liquidity",
        expression="balance_sheet.cash_and_equivalents / balance_sheet.total_current_liabilities",
        description="Cash and equivalents divided by current liabilities. Most conservative liquidity measure.",
        required_fields=[
            "balance_sheet.cash_and_equivalents",
            "balance_sheet.total_current_liabilities",
        ],
        example=">= 0.2",
    ),
]

# ── Solvency / Leverage ─────────────────────────────────────────

_SOLVENCY: list[BuiltinFormula] = [
    BuiltinFormula(
        name="debt_to_equity",
        category="solvency",
        expression="balance_sheet.long_term_debt / balance_sheet.total_equity",
        description="Long-term debt relative to shareholder equity.",
        required_fields=["balance_sheet.long_term_debt", "balance_sheet.total_equity"],
        example="<= 1.0",
    ),
    BuiltinFormula(
        name="total_debt_to_equity",
        category="solvency",
        expression=(
            "(balance_sheet.short_term_debt + balance_sheet.long_term_debt)"
            " / balance_sheet.total_equity"
        ),
        description="Total debt (short + long term) relative to shareholder equity.",
        required_fields=[
            "balance_sheet.short_term_debt",
            "balance_sheet.long_term_debt",
            "balance_sheet.total_equity",
        ],
        example="<= 1.5",
    ),
    BuiltinFormula(
        name="debt_to_assets",
        category="solvency",
        expression="balance_sheet.total_liabilities / balance_sheet.total_assets",
        description="Total liabilities relative to total assets.",
        required_fields=["balance_sheet.total_liabilities", "balance_sheet.total_assets"],
        example="<= 0.60",
    ),
    BuiltinFormula(
        name="interest_coverage",
        category="solvency",
        expression="income_statement.operating_income / income_statement.interest_expense",
        description="Operating income divided by interest expense. Measures ability to service debt.",
        required_fields=[
            "income_statement.operating_income",
            "income_statement.interest_expense",
        ],
        example=">= 5.0",
    ),
]

# ── Efficiency ───────────────────────────────────────────────────

_EFFICIENCY: list[BuiltinFormula] = [
    BuiltinFormula(
        name="asset_turnover",
        category="efficiency",
        expression="income_statement.revenue / balance_sheet.total_assets",
        description="Revenue generated per dollar of assets.",
        required_fields=["income_statement.revenue", "balance_sheet.total_assets"],
        example=">= 0.5",
    ),
    BuiltinFormula(
        name="inventory_turnover",
        category="efficiency",
        expression="income_statement.cost_of_revenue / balance_sheet.inventory",
        description="Cost of goods sold divided by inventory. Higher means faster inventory turns.",
        required_fields=["income_statement.cost_of_revenue", "balance_sheet.inventory"],
        example=">= 5.0",
    ),
    BuiltinFormula(
        name="receivables_turnover",
        category="efficiency",
        expression="income_statement.revenue / balance_sheet.accounts_receivable",
        description="Revenue divided by accounts receivable. Measures collection efficiency.",
        required_fields=[
            "income_statement.revenue",
            "balance_sheet.accounts_receivable",
        ],
        example=">= 8.0",
    ),
]

# ── Cash Flow Quality ────────────────────────────────────────────

_CASH_FLOW: list[BuiltinFormula] = [
    BuiltinFormula(
        name="fcf_margin",
        category="quality",
        expression="cash_flow.free_cash_flow / income_statement.revenue",
        description="Free cash flow as a percentage of revenue.",
        required_fields=["cash_flow.free_cash_flow", "income_statement.revenue"],
        example=">= 0.10 (10%)",
    ),
    BuiltinFormula(
        name="operating_cash_flow_ratio",
        category="quality",
        expression="cash_flow.operating_cash_flow / income_statement.net_income",
        description=(
            "Operating cash flow relative to net income. "
            "> 1.0 indicates strong cash conversion."
        ),
        required_fields=["cash_flow.operating_cash_flow", "income_statement.net_income"],
        example=">= 1.0",
    ),
    BuiltinFormula(
        name="capex_to_revenue",
        category="quality",
        expression="abs(cash_flow.capital_expenditure) / income_statement.revenue",
        description="Capital expenditure as a percentage of revenue. Lower is better for capital-light businesses.",
        required_fields=["cash_flow.capital_expenditure", "income_statement.revenue"],
        example="<= 0.10",
    ),
    BuiltinFormula(
        name="fcf_to_net_income",
        category="quality",
        expression="cash_flow.free_cash_flow / income_statement.net_income",
        description=(
            "Free cash flow relative to net income. "
            "> 1.0 indicates FCF exceeds reported earnings."
        ),
        required_fields=["cash_flow.free_cash_flow", "income_statement.net_income"],
        example=">= 0.80",
    ),
]

# ── Dividend ─────────────────────────────────────────────────────

_DIVIDEND: list[BuiltinFormula] = [
    BuiltinFormula(
        name="dividend_payout_ratio",
        category="dividend",
        expression="abs(cash_flow.dividends_paid) / income_statement.net_income",
        description="Dividends paid as a percentage of net income.",
        required_fields=["cash_flow.dividends_paid", "income_statement.net_income"],
        example="between 0.20 and 0.60",
    ),
    BuiltinFormula(
        name="buyback_yield",
        category="dividend",
        expression=(
            "abs(cash_flow.share_buybacks) / "
            "(income_statement.eps_diluted * income_statement.shares_outstanding_diluted)"
        ),
        description="Share buybacks relative to approximate market cap (earnings-based proxy).",
        required_fields=[
            "cash_flow.share_buybacks",
            "income_statement.eps_diluted",
            "income_statement.shares_outstanding_diluted",
        ],
    ),
]

# ── Composite / Special ──────────────────────────────────────────

_COMPOSITE: list[BuiltinFormula] = [
    BuiltinFormula(
        name="sbc_to_revenue",
        category="quality",
        expression="cash_flow.stock_based_compensation / income_statement.revenue",
        description=(
            "Stock-based compensation as a percentage of revenue. "
            "> 10% is a red flag for many investors."
        ),
        required_fields=[
            "cash_flow.stock_based_compensation",
            "income_statement.revenue",
        ],
        example="<= 0.05",
    ),
    BuiltinFormula(
        name="rd_to_revenue",
        category="quality",
        expression="income_statement.research_and_development / income_statement.revenue",
        description="R&D spending as a percentage of revenue. Varies significantly by industry.",
        required_fields=[
            "income_statement.research_and_development",
            "income_statement.revenue",
        ],
    ),
]

# ── Registry ─────────────────────────────────────────────────────

ALL_BUILTIN_FORMULAS: list[BuiltinFormula] = (
    _PROFITABILITY
    + _GROWTH
    + _LIQUIDITY
    + _SOLVENCY
    + _EFFICIENCY
    + _CASH_FLOW
    + _DIVIDEND
    + _COMPOSITE
)

FORMULA_REGISTRY: dict[str, BuiltinFormula] = {f.name: f for f in ALL_BUILTIN_FORMULAS}


def get_formula(name: str) -> BuiltinFormula | None:
    """Look up a built-in formula by name."""
    return FORMULA_REGISTRY.get(name)


def resolve_expression(formula_name_or_expr: str, *, is_custom: bool = False) -> str:
    """Resolve a formula name to its expression, or return custom expression as-is.

    Args:
        formula_name_or_expr: Built-in formula name or custom expression string.
        is_custom: If True, treat as a raw custom expression.

    Returns:
        The resolved expression string.

    Raises:
        ValueError: If not custom and the name is not in the registry.
    """
    if is_custom:
        return formula_name_or_expr

    builtin = FORMULA_REGISTRY.get(formula_name_or_expr)
    if builtin is None:
        msg = f"Unknown built-in formula: {formula_name_or_expr!r}"
        raise ValueError(msg)
    return builtin.expression
