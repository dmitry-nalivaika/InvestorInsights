# Built-in Financial Formulas

> Referenced from [Plan](../plan.md) — Analysis Engine section

## Profitability

| Name | Formula | Required Fields | Unit | Typical Range | Notes |
|------|---------|-----------------|------|---------------|-------|
| `gross_margin` | `income_statement.gross_profit / income_statement.revenue` | gross_profit, revenue | ratio | 0.20–0.80 | Example threshold: `>= 0.40 (40%)` |
| `operating_margin` | `income_statement.operating_income / income_statement.revenue` | operating_income, revenue | ratio | 0.05–0.40 | |
| `net_margin` | `income_statement.net_income / income_statement.revenue` | net_income, revenue | ratio | 0.03–0.30 | |
| `roe` | `income_statement.net_income / balance_sheet.total_equity` | net_income, total_equity | ratio | 0.08–0.40 | Negative equity makes ROE misleading |
| `roa` | `income_statement.net_income / balance_sheet.total_assets` | net_income, total_assets | ratio | 0.03–0.20 | |
| `roic` | `(income_statement.operating_income * (1 - 0.21)) / (balance_sheet.total_assets - balance_sheet.total_current_liabilities - balance_sheet.cash_and_equivalents)` | operating_income, total_assets, total_current_liabilities, cash_and_equivalents | ratio | 0.08–0.30 | Uses statutory 21% tax rate as approximation |

## Growth

| Name | Formula | Required Fields | Unit | Notes |
|------|---------|-----------------|------|-------|
| `revenue_growth` | `(income_statement.revenue - prev(income_statement.revenue)) / prev(income_statement.revenue)` | revenue | ratio | Requires prior period |
| `earnings_growth` | `(income_statement.net_income - prev(income_statement.net_income)) / abs(prev(income_statement.net_income))` | net_income | ratio | Requires prior period |
| `operating_income_growth` | `(income_statement.operating_income - prev(income_statement.operating_income)) / abs(prev(income_statement.operating_income))` | operating_income | ratio | Requires prior period |
| `fcf_growth` | `(cash_flow.free_cash_flow - prev(cash_flow.free_cash_flow)) / abs(prev(cash_flow.free_cash_flow))` | free_cash_flow | ratio | Requires prior period |

## Liquidity

| Name | Formula | Required Fields | Unit | Typical Range | Notes |
|------|---------|-----------------|------|---------------|-------|
| `current_ratio` | `balance_sheet.total_current_assets / balance_sheet.total_current_liabilities` | total_current_assets, total_current_liabilities | ratio | 1.0–3.0 | |
| `quick_ratio` | `(balance_sheet.total_current_assets - balance_sheet.inventory) / balance_sheet.total_current_liabilities` | total_current_assets, inventory, total_current_liabilities | ratio | — | |
| `cash_ratio` | `balance_sheet.cash_and_equivalents / balance_sheet.total_current_liabilities` | cash_and_equivalents, total_current_liabilities | ratio | — | |

## Solvency / Leverage

| Name | Formula | Required Fields | Unit | Typical Range | Notes |
|------|---------|-----------------|------|---------------|-------|
| `debt_to_equity` | `balance_sheet.long_term_debt / balance_sheet.total_equity` | long_term_debt, total_equity | ratio | 0–2.0 | |
| `total_debt_to_equity` | `(balance_sheet.short_term_debt + balance_sheet.long_term_debt) / balance_sheet.total_equity` | short_term_debt, long_term_debt, total_equity | ratio | — | |
| `debt_to_assets` | `balance_sheet.total_liabilities / balance_sheet.total_assets` | total_liabilities, total_assets | ratio | 0.20–0.70 | |
| `interest_coverage` | `income_statement.operating_income / income_statement.interest_expense` | operating_income, interest_expense | times | 3.0–50.0 | Higher is better. < 1.5 is concerning. |

## Efficiency

| Name | Formula | Required Fields | Unit | Notes |
|------|---------|-----------------|------|-------|
| `asset_turnover` | `income_statement.revenue / balance_sheet.total_assets` | revenue, total_assets | times | |
| `inventory_turnover` | `income_statement.cost_of_revenue / balance_sheet.inventory` | cost_of_revenue, inventory | times | Not applicable for service companies (inventory may be 0) |
| `receivables_turnover` | `income_statement.revenue / balance_sheet.accounts_receivable` | revenue, accounts_receivable | times | |

## Cash Flow Quality

| Name | Formula | Required Fields | Unit | Typical Range | Notes |
|------|---------|-----------------|------|---------------|-------|
| `fcf_margin` | `cash_flow.free_cash_flow / income_statement.revenue` | free_cash_flow, revenue | ratio | 0.05–0.35 | |
| `operating_cash_flow_ratio` | `cash_flow.operating_cash_flow / income_statement.net_income` | operating_cash_flow, net_income | ratio | — | > 1.0 indicates strong cash conversion |
| `capex_to_revenue` | `abs(cash_flow.capital_expenditure) / income_statement.revenue` | capital_expenditure, revenue | ratio | — | Lower is generally better for capital-light businesses |
| `fcf_to_net_income` | `cash_flow.free_cash_flow / income_statement.net_income` | free_cash_flow, net_income | ratio | — | > 1.0 indicates FCF exceeds reported earnings |

## Dividend

| Name | Formula | Required Fields | Unit | Typical Range | Notes |
|------|---------|-----------------|------|---------------|-------|
| `dividend_payout_ratio` | `abs(cash_flow.dividends_paid) / income_statement.net_income` | dividends_paid, net_income | ratio | 0.20–0.60 | |
| `buyback_yield` | `abs(cash_flow.share_buybacks) / (income_statement.eps_diluted * income_statement.shares_outstanding_diluted)` | share_buybacks, eps_diluted, shares_outstanding_diluted | ratio | — | Approximation using earnings-based market cap proxy. Not precise. |

## Composite / Special

| Name | Formula | Required Fields | Unit | Notes |
|------|---------|-----------------|------|-------|
| `sbc_to_revenue` | `cash_flow.stock_based_compensation / income_statement.revenue` | stock_based_compensation, revenue | ratio | High SBC dilutes shareholders. > 10% is a red flag for many investors. |
| `rd_to_revenue` | `income_statement.research_and_development / income_statement.revenue` | research_and_development, revenue | ratio | Varies significantly by industry. Tech typically 10–25%. |
