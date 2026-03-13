# Appendix B: XBRL Tag Mapping

> Referenced from [System Specification](../system_specification.md)

Maps US-GAAP XBRL taxonomy tags to internal financial data fields.  
Some concepts have multiple possible tags (companies may use different ones).  
**Priority:** first matching tag wins.

---

## Income Statement

| Internal Field | XBRL Tags (priority order) | Period Type |
|----------------|---------------------------|-------------|
| `revenue` | `us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax`, `us-gaap:Revenues`, `us-gaap:SalesRevenueNet`, `us-gaap:RevenueFromContractWithCustomerIncludingAssessedTax` | duration |
| `cost_of_revenue` | `us-gaap:CostOfGoodsAndServicesSold`, `us-gaap:CostOfRevenue`, `us-gaap:CostOfGoodsSold` | duration |
| `gross_profit` | `us-gaap:GrossProfit` | duration |
| `research_and_development` | `us-gaap:ResearchAndDevelopmentExpense`, `us-gaap:ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost` | duration |
| `selling_general_admin` | `us-gaap:SellingGeneralAndAdministrativeExpense`, `us-gaap:GeneralAndAdministrativeExpense` | duration |
| `operating_income` | `us-gaap:OperatingIncomeLoss` | duration |
| `interest_expense` | `us-gaap:InterestExpense`, `us-gaap:InterestExpenseDebt` | duration |
| `interest_income` | `us-gaap:InvestmentIncomeInterest`, `us-gaap:InterestIncomeExpenseNet` | duration |
| `income_before_tax` | `us-gaap:IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest`, `us-gaap:IncomeLossFromContinuingOperationsBeforeIncomeTaxesDomestic` | duration |
| `income_tax_expense` | `us-gaap:IncomeTaxExpenseBenefit` | duration |
| `net_income` | `us-gaap:NetIncomeLoss`, `us-gaap:ProfitLoss` | duration |
| `eps_basic` | `us-gaap:EarningsPerShareBasic` | duration (per-share) |
| `eps_diluted` | `us-gaap:EarningsPerShareDiluted` | duration (per-share) |
| `shares_outstanding_basic` | `us-gaap:WeightedAverageNumberOfShareOutstandingBasicAndDiluted`, `us-gaap:WeightedAverageNumberOfSharesOutstandingBasic` | duration |
| `shares_outstanding_diluted` | `us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding` | duration |
| `depreciation_amortization` | `us-gaap:DepreciationDepletionAndAmortization`, `us-gaap:DepreciationAmortizationAndAccretionNet` | duration |

### Fallback Formulas

| Field | Fallback |
|-------|----------|
| `gross_profit` | `revenue - cost_of_revenue` |

---

## Balance Sheet

| Internal Field | XBRL Tags (priority order) | Period Type |
|----------------|---------------------------|-------------|
| `cash_and_equivalents` | `us-gaap:CashAndCashEquivalentsAtCarryingValue`, `us-gaap:Cash` | instant |
| `short_term_investments` | `us-gaap:ShortTermInvestments`, `us-gaap:AvailableForSaleSecuritiesDebtSecuritiesCurrent` | instant |
| `accounts_receivable` | `us-gaap:AccountsReceivableNetCurrent`, `us-gaap:ReceivablesNetCurrent` | instant |
| `inventory` | `us-gaap:InventoryNet`, `us-gaap:InventoryFinishedGoodsNetOfReserves` | instant |
| `total_current_assets` | `us-gaap:AssetsCurrent` | instant |
| `property_plant_equipment` | `us-gaap:PropertyPlantAndEquipmentNet` | instant |
| `goodwill` | `us-gaap:Goodwill` | instant |
| `intangible_assets` | `us-gaap:IntangibleAssetsNetExcludingGoodwill`, `us-gaap:FiniteLivedIntangibleAssetsNet` | instant |
| `total_assets` | `us-gaap:Assets` | instant |
| `accounts_payable` | `us-gaap:AccountsPayableCurrent` | instant |
| `short_term_debt` | `us-gaap:ShortTermBorrowings`, `us-gaap:LongTermDebtCurrent`, `us-gaap:DebtCurrent` | instant |
| `total_current_liabilities` | `us-gaap:LiabilitiesCurrent` | instant |
| `long_term_debt` | `us-gaap:LongTermDebtNoncurrent`, `us-gaap:LongTermDebt` | instant |
| `total_liabilities` | `us-gaap:Liabilities` | instant |
| `total_equity` | `us-gaap:StockholdersEquity`, `us-gaap:StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest` | instant |
| `retained_earnings` | `us-gaap:RetainedEarningsAccumulatedDeficit` | instant |
| `common_stock` | `us-gaap:CommonStocksIncludingAdditionalPaidInCapital`, `us-gaap:CommonStockValue` | instant |

---

## Cash Flow

| Internal Field | XBRL Tags (priority order) | Period Type | Notes |
|----------------|---------------------------|-------------|-------|
| `operating_cash_flow` | `us-gaap:NetCashProvidedByUsedInOperatingActivities` | duration | |
| `capital_expenditure` | `us-gaap:PaymentsToAcquirePropertyPlantAndEquipment`, `us-gaap:PaymentsToAcquireProductiveAssets` | duration | Negate: typically reported as positive, store as negative |
| `investing_cash_flow` | `us-gaap:NetCashProvidedByUsedInInvestingActivities` | duration | |
| `financing_cash_flow` | `us-gaap:NetCashProvidedByUsedInFinancingActivities` | duration | |
| `dividends_paid` | `us-gaap:PaymentsOfDividendsCommonStock`, `us-gaap:PaymentsOfDividends` | duration | Negate |
| `share_buybacks` | `us-gaap:PaymentsForRepurchaseOfCommonStock`, `us-gaap:PaymentsForRepurchaseOfEquity` | duration | Negate |
| `debt_issued` | `us-gaap:ProceedsFromIssuanceOfLongTermDebt`, `us-gaap:ProceedsFromDebtNetOfIssuanceCosts` | duration | |
| `debt_repaid` | `us-gaap:RepaymentsOfLongTermDebt`, `us-gaap:RepaymentsOfDebt` | duration | Negate |
| `stock_based_compensation` | `us-gaap:ShareBasedCompensation`, `us-gaap:AllocatedShareBasedCompensationExpense` | duration | |
| `free_cash_flow` | *(Not a standard XBRL tag)* | — | Computed: `operating_cash_flow + capital_expenditure` |

---

## Period Selection Rules

### Annual

- Select facts where duration is approximately **12 months** (365 ± 30 days).
- For instant items, select the **end-of-fiscal-year** date.

```
duration_days_min: 335
duration_days_max: 395
```

### Quarterly

- Select facts where duration is approximately **3 months** (90 ± 15 days).

```
duration_days_min: 75
duration_days_max: 105
```

### Disambiguation

When multiple values exist for the same period:

1. Prefer values from the company's own filing (not amendments).
2. Prefer values with form type `10-K` over `10-K/A`.
3. Prefer the most recently filed value.

```
priority:
  - same_fiscal_period_latest_filing
  - exclude_amendments_if_original_exists
```
