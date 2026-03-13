# Appendix D: Default Analysis Profile Template

> Referenced from [System Specification](../system_specification.md)

This profile is seeded into the system on first startup.  
Users can modify it or create their own.

---

## Profile: Quality Value Investor

**Description:**  
A balanced analysis profile for quality-focused value investors. Evaluates profitability, capital efficiency, financial health, growth, and cash flow quality. Suitable for established companies with 5+ years of financial history.

**Default:** Yes

---

### Criteria

#### Profitability (weight emphasis)

| # | Name | Formula | Comparison | Threshold | Weight | Lookback |
|---|------|---------|------------|-----------|--------|----------|
| 1 | Gross Margin > 40% | `gross_margin` | `>=` | 0.40 | 2.0 | 5 years |
| 2 | Operating Margin > 15% | `operating_margin` | `>=` | 0.15 | 2.0 | 5 years |
| 3 | Net Margin > 10% | `net_margin` | `>=` | 0.10 | 1.5 | 5 years |
| 4 | ROE > 15% | `roe` | `>=` | 0.15 | 2.5 | 5 years |
| 5 | ROIC > 12% | `roic` | `>=` | 0.12 | 3.0 | 5 years |

**Notes:**
- *Gross Margin > 40%:* High gross margin indicates pricing power and competitive advantage.
- *Operating Margin > 15%:* Strong operating efficiency.
- *Net Margin > 10%:* Healthy bottom-line profitability.
- *ROE > 15%:* Strong return on shareholder equity.
- *ROIC > 12%:* Creating value above cost of capital.

#### Growth

| # | Name | Formula | Comparison | Threshold | Weight | Lookback |
|---|------|---------|------------|-----------|--------|----------|
| 6 | Revenue Growth > 5% | `revenue_growth` | `>=` | 0.05 | 1.5 | 5 years |
| 7 | Earnings Growth Positive | `earnings_growth` | `>` | 0.0 | 1.0 | 5 years |
| 8 | Revenue Trend Improving | `revenue_growth` | `trend_up` | — | 1.0 | 5 years |

**Notes:**
- *Revenue Growth > 5%:* Moderate top-line growth.
- *Earnings Growth Positive:* Growing earnings year over year.
- *Revenue Trend Improving:* Revenue shows upward trend over multiple years.

#### Solvency / Leverage

| # | Name | Formula | Comparison | Threshold | Weight | Lookback |
|---|------|---------|------------|-----------|--------|----------|
| 9 | Debt-to-Equity < 1.0 | `debt_to_equity` | `<=` | 1.0 | 2.0 | 5 years |
| 10 | Interest Coverage > 5x | `interest_coverage` | `>=` | 5.0 | 1.5 | 5 years |

**Notes:**
- *Debt-to-Equity < 1.0:* Conservative leverage — debt less than equity.
- *Interest Coverage > 5x:* Comfortable ability to service debt obligations.

#### Liquidity

| # | Name | Formula | Comparison | Threshold | Weight | Lookback |
|---|------|---------|------------|-----------|--------|----------|
| 11 | Current Ratio > 1.2 | `current_ratio` | `>=` | 1.2 | 1.0 | 3 years |

**Notes:**
- *Current Ratio > 1.2:* Adequate short-term liquidity.

#### Cash Flow Quality

| # | Name | Formula | Comparison | Threshold | Weight | Lookback |
|---|------|---------|------------|-----------|--------|----------|
| 12 | FCF Margin > 10% | `fcf_margin` | `>=` | 0.10 | 2.5 | 5 years |
| 13 | OCF > Net Income | `operating_cash_flow_ratio` | `>=` | 1.0 | 2.0 | 5 years |
| 14 | FCF Conversion > 80% | `fcf_to_net_income` | `>=` | 0.80 | 1.5 | 5 years |
| 15 | SBC < 5% of Revenue | `sbc_to_revenue` | `<=` | 0.05 | 1.0 | 3 years |

**Notes:**
- *FCF Margin > 10%:* Strong free cash flow generation relative to revenue.
- *OCF > Net Income:* Cash earnings exceed accrual earnings (quality indicator).
- *FCF Conversion > 80%:* FCF is at least 80% of net income.
- *SBC < 5% of Revenue:* Stock-based compensation is not excessive.

---

### Profile Summary

| Metric | Value |
|--------|-------|
| Total Criteria | 15 |
| Total Weight | 24.5 |
| Max Possible Score | 24.5 |
| Categories Covered | Profitability, Growth, Solvency, Liquidity, Quality |
