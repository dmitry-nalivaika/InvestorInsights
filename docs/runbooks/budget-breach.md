# Budget Breach Runbook

> **Target**: Dev environment ≤ $50/month (Constitution IV, SC-010)
>
> This runbook documents manual cost-reduction procedures when the monthly
> Azure spend approaches or exceeds the $50 development budget threshold.

---

## 1. Check Current Spend

```bash
# Via Makefile
make azure-cost

# Direct CLI
az consumption usage list \
    --start-date $(date -v-30d +%Y-%m-%d) --end-date $(date +%Y-%m-%d) \
    --query "[?contains(instanceName,'investorinsights')].{Name:instanceName, Cost:pretaxCost, Currency:currency}" \
    --output table
```

Azure Budget alerts are configured at:
- **80% ($40)** — Warning: review usage, consider preemptive scaling
- **100% ($50)** — Critical: execute cost reduction immediately

---

## 2. Scale-to-Zero Procedure

When immediate cost reduction is needed, scale down non-essential Container Apps:

```bash
ENV=dev
RG="rg-investorinsights-${ENV}"

# Scale API to 0 replicas (stops billing for Container Apps compute)
az containerapp update --name api --resource-group $RG \
    --min-replicas 0 --max-replicas 0

# Scale worker to 0 replicas
az containerapp update --name worker --resource-group $RG \
    --min-replicas 0 --max-replicas 0

# Scale frontend to 0 replicas
az containerapp update --name frontend --resource-group $RG \
    --min-replicas 0 --max-replicas 0
```

**Impact**: All services become unavailable. No new ingestion or chat requests.

### Restore from Scale-to-Zero

```bash
# Restore API (1 replica)
az containerapp update --name api --resource-group $RG \
    --min-replicas 1 --max-replicas 2

# Restore worker
az containerapp update --name worker --resource-group $RG \
    --min-replicas 1 --max-replicas 1

# Restore frontend
az containerapp update --name frontend --resource-group $RG \
    --min-replicas 1 --max-replicas 1
```

---

## 3. Switch LLM to Lower-Cost Model

If OpenAI costs are the primary driver, switch to gpt-4o-mini (already default):

```bash
# Update the Container App environment variable
az containerapp update --name api --resource-group $RG \
    --set-env-vars "LLM_MODEL=gpt-4o-mini" \
                   "AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4o-mini"
```

If already on gpt-4o-mini, further cost options:
- Reduce `LLM_MAX_TOKENS` from 4096 to 2048
- Reduce `RAG_TOP_K` from 15 to 5 (fewer embedding lookups)
- Disable AI summaries in analysis runs (`generate_summary: false`)

---

## 4. Remove Redis (Optional)

Redis is used for caching, rate limiting, and Celery task broker. It's a
non-critical dependency — the platform degrades gracefully without it:

- **Rate limiting**: Fails open (all requests allowed)
- **Caching**: Cache misses — slightly slower responses
- **Celery tasks**: Cannot dispatch async ingestion tasks

```bash
# Scale Redis container to 0
az containerapp update --name redis --resource-group $RG \
    --min-replicas 0 --max-replicas 0
```

**Impact**: Background document ingestion stops. Chat and analysis still work.
Rate limits are not enforced.

### Restore Redis

```bash
az containerapp update --name redis --resource-group $RG \
    --min-replicas 1 --max-replicas 1
```

---

## 5. Reduce PostgreSQL Tier

If database costs are significant:

```bash
# Downgrade to Burstable B1ms (smallest available)
az postgres flexible-server update \
    --name investorinsights-pg-dev \
    --resource-group $RG \
    --sku-name Standard_B1ms
```

**Note**: This may cause a brief downtime during the tier change.

---

## 6. Reduce Qdrant Resources

```bash
az containerapp update --name qdrant --resource-group $RG \
    --cpu 0.25 --memory 0.5Gi
```

---

## 7. Cost Breakdown Reference (Dev Environment)

| Resource | Estimated Monthly | Notes |
|----------|-------------------|-------|
| PostgreSQL B1ms | ~$13 | Burstable, auto-pause not available |
| Container Apps (3 apps) | ~$10-15 | 0.5 vCPU each, scale-to-zero |
| Azure OpenAI | ~$5-15 | Usage-based, gpt-4o-mini is cheapest |
| Azure Blob Storage | ~$1 | LRS, minimal data |
| Container Registry | ~$5 | Basic tier |
| Qdrant Container App | ~$3-5 | 0.5 vCPU |
| Redis Container App | ~$2-3 | 0.25 vCPU |
| **Total** | **~$40-55** | |

---

## 8. Emergency: Full Teardown

If the budget is severely exceeded and no further spend is acceptable:

```bash
# ⚠️ WARNING: This destroys ALL resources including data
make azure-destroy ENV=dev
```

This runs `infra/scripts/destroy.sh` which deletes the entire resource group.

**Before teardown, export any data you want to keep:**

```bash
# Export database
az postgres flexible-server execute \
    --name investorinsights-pg-dev \
    --resource-group $RG \
    --admin-user analyst \
    --admin-password "$DB_PASSWORD" \
    --querytext "COPY (SELECT * FROM companies) TO STDOUT WITH CSV HEADER"
```
