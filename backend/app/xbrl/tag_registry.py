# filepath: backend/app/xbrl/tag_registry.py
"""XBRL tag registry — maps US-GAAP XBRL tags to internal field names.

Based on reference/xbrl-tag-mapping.md. Each internal field has a
prioritised list of XBRL tags that may contain its value.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TagMapping:
    """Mapping from internal field name to XBRL tags."""

    internal_field: str
    xbrl_tags: list[str]
    period_type: str  # "duration" or "instant"
    statement: str    # "income_statement", "balance_sheet", "cash_flow"
    negate: bool = False  # Some cash flow items need sign inversion


# ── Income Statement ─────────────────────────────────────────────

INCOME_STATEMENT_MAPPINGS: list[TagMapping] = [
    TagMapping("revenue", [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
    ], "duration", "income_statement"),
    TagMapping("cost_of_revenue", [
        "CostOfGoodsAndServicesSold",
        "CostOfRevenue",
        "CostOfGoodsSold",
    ], "duration", "income_statement"),
    TagMapping("gross_profit", [
        "GrossProfit",
    ], "duration", "income_statement"),
    TagMapping("research_and_development", [
        "ResearchAndDevelopmentExpense",
        "ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost",
    ], "duration", "income_statement"),
    TagMapping("selling_general_admin", [
        "SellingGeneralAndAdministrativeExpense",
        "GeneralAndAdministrativeExpense",
    ], "duration", "income_statement"),
    TagMapping("operating_income", [
        "OperatingIncomeLoss",
    ], "duration", "income_statement"),
    TagMapping("interest_expense", [
        "InterestExpense",
        "InterestExpenseDebt",
    ], "duration", "income_statement"),
    TagMapping("interest_income", [
        "InvestmentIncomeInterest",
        "InterestIncomeExpenseNet",
    ], "duration", "income_statement"),
    TagMapping("income_before_tax", [
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesDomestic",
    ], "duration", "income_statement"),
    TagMapping("income_tax_expense", [
        "IncomeTaxExpenseBenefit",
    ], "duration", "income_statement"),
    TagMapping("net_income", [
        "NetIncomeLoss",
        "ProfitLoss",
    ], "duration", "income_statement"),
    TagMapping("eps_basic", [
        "EarningsPerShareBasic",
    ], "duration", "income_statement"),
    TagMapping("eps_diluted", [
        "EarningsPerShareDiluted",
    ], "duration", "income_statement"),
    TagMapping("shares_outstanding_basic", [
        "WeightedAverageNumberOfShareOutstandingBasicAndDiluted",
        "WeightedAverageNumberOfSharesOutstandingBasic",
    ], "duration", "income_statement"),
    TagMapping("shares_outstanding_diluted", [
        "WeightedAverageNumberOfDilutedSharesOutstanding",
    ], "duration", "income_statement"),
    TagMapping("depreciation_amortization", [
        "DepreciationDepletionAndAmortization",
        "DepreciationAmortizationAndAccretionNet",
    ], "duration", "income_statement"),
]

# ── Balance Sheet ────────────────────────────────────────────────

BALANCE_SHEET_MAPPINGS: list[TagMapping] = [
    TagMapping("cash_and_equivalents", [
        "CashAndCashEquivalentsAtCarryingValue",
        "Cash",
    ], "instant", "balance_sheet"),
    TagMapping("short_term_investments", [
        "ShortTermInvestments",
        "AvailableForSaleSecuritiesDebtSecuritiesCurrent",
    ], "instant", "balance_sheet"),
    TagMapping("accounts_receivable", [
        "AccountsReceivableNetCurrent",
        "ReceivablesNetCurrent",
    ], "instant", "balance_sheet"),
    TagMapping("inventory", [
        "InventoryNet",
        "InventoryFinishedGoodsNetOfReserves",
    ], "instant", "balance_sheet"),
    TagMapping("total_current_assets", [
        "AssetsCurrent",
    ], "instant", "balance_sheet"),
    TagMapping("property_plant_equipment", [
        "PropertyPlantAndEquipmentNet",
    ], "instant", "balance_sheet"),
    TagMapping("goodwill", [
        "Goodwill",
    ], "instant", "balance_sheet"),
    TagMapping("intangible_assets", [
        "IntangibleAssetsNetExcludingGoodwill",
        "FiniteLivedIntangibleAssetsNet",
    ], "instant", "balance_sheet"),
    TagMapping("total_assets", [
        "Assets",
    ], "instant", "balance_sheet"),
    TagMapping("accounts_payable", [
        "AccountsPayableCurrent",
    ], "instant", "balance_sheet"),
    TagMapping("short_term_debt", [
        "ShortTermBorrowings",
        "LongTermDebtCurrent",
        "DebtCurrent",
    ], "instant", "balance_sheet"),
    TagMapping("total_current_liabilities", [
        "LiabilitiesCurrent",
    ], "instant", "balance_sheet"),
    TagMapping("long_term_debt", [
        "LongTermDebtNoncurrent",
        "LongTermDebt",
    ], "instant", "balance_sheet"),
    TagMapping("total_liabilities", [
        "Liabilities",
    ], "instant", "balance_sheet"),
    TagMapping("total_equity", [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ], "instant", "balance_sheet"),
    TagMapping("retained_earnings", [
        "RetainedEarningsAccumulatedDeficit",
    ], "instant", "balance_sheet"),
    TagMapping("common_stock", [
        "CommonStocksIncludingAdditionalPaidInCapital",
        "CommonStockValue",
    ], "instant", "balance_sheet"),
]

# ── Cash Flow ────────────────────────────────────────────────────

CASH_FLOW_MAPPINGS: list[TagMapping] = [
    TagMapping("operating_cash_flow", [
        "NetCashProvidedByUsedInOperatingActivities",
    ], "duration", "cash_flow"),
    TagMapping("capital_expenditure", [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
    ], "duration", "cash_flow", negate=True),
    TagMapping("investing_cash_flow", [
        "NetCashProvidedByUsedInInvestingActivities",
    ], "duration", "cash_flow"),
    TagMapping("financing_cash_flow", [
        "NetCashProvidedByUsedInFinancingActivities",
    ], "duration", "cash_flow"),
    TagMapping("dividends_paid", [
        "PaymentsOfDividendsCommonStock",
        "PaymentsOfDividends",
    ], "duration", "cash_flow", negate=True),
    TagMapping("share_buybacks", [
        "PaymentsForRepurchaseOfCommonStock",
        "PaymentsForRepurchaseOfEquity",
    ], "duration", "cash_flow", negate=True),
    TagMapping("debt_issued", [
        "ProceedsFromIssuanceOfLongTermDebt",
        "ProceedsFromDebtNetOfIssuanceCosts",
    ], "duration", "cash_flow"),
    TagMapping("debt_repaid", [
        "RepaymentsOfLongTermDebt",
        "RepaymentsOfDebt",
    ], "duration", "cash_flow", negate=True),
    TagMapping("stock_based_compensation", [
        "ShareBasedCompensation",
        "AllocatedShareBasedCompensationExpense",
    ], "duration", "cash_flow"),
]

# ── All mappings combined ────────────────────────────────────────

ALL_MAPPINGS: list[TagMapping] = (
    INCOME_STATEMENT_MAPPINGS
    + BALANCE_SHEET_MAPPINGS
    + CASH_FLOW_MAPPINGS
)

# Build a quick lookup: xbrl_tag -> TagMapping
TAG_TO_MAPPING: dict[str, TagMapping] = {}
for _mapping in ALL_MAPPINGS:
    for _tag in _mapping.xbrl_tags:
        if _tag not in TAG_TO_MAPPING:
            TAG_TO_MAPPING[_tag] = _mapping
