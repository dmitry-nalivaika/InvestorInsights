# Azure Portal Dashboards — T808

## Files

| Dashboard | File | Purpose |
|-----------|------|---------|
| Operations | `operations.json` | Real-time API health, latency, DB metrics, error rates |

## How to Import

1. Open [Azure Portal](https://portal.azure.com) → **Dashboard**
2. Click **Upload** (top bar)
3. Select `operations.json`
4. The dashboard appears — pin your specific resource instances to each tile

## Tiles Overview

| Row | Left (cols 0-5) | Right (cols 6-11) |
|-----|-----------------|-------------------|
| 0 | Platform Health (Markdown) | Request Rate & Failures |
| 1 | API Response Time p50/p95/p99 | PostgreSQL CPU & Connections |
| 2 | PostgreSQL Storage & Memory | Container Apps Replicas & CPU |
| 3 | Request Summary Table (full width) | |
| 4 | Chat Endpoint Latency (full width) | |
| 5 | Error Breakdown 4xx/5xx (full width) | |

## Customisation

After importing, click **Edit** on each metric tile to bind it to your
specific App Insights / PostgreSQL / Container Apps resource instance.

The Kusto queries in the log-based tiles (rows 3–5) work out of the box
once bound to your Application Insights workspace.

## Alert Correlation

The dashboard pairs with the alert rules in `infra/modules/alerts.bicep`:
- HTTP 5xx spike → row 1 right tile
- API p95 > 2s → row 1 left tile
- DB CPU > 80% → row 2 right tile
- Chat TTFT > 5s → row 4 tile
