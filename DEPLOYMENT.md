# Azure Deployment Guide

> Step-by-step guide for deploying InvestorInsights to Azure.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [1. Azure Infrastructure (Bicep)](#1-azure-infrastructure-bicep)
- [2. Seed Key Vault Secrets](#2-seed-key-vault-secrets)
- [3. Database Migration](#3-database-migration)
- [4. Build & Push Docker Images](#4-build--push-docker-images)
- [5. Deploy Container Apps](#5-deploy-container-apps)
- [6. Verification](#6-verification)
- [7. Updating](#7-updating)
- [8. Teardown](#8-teardown)
- [Architecture Overview](#architecture-overview)
- [Cost Estimates](#cost-estimates)

---

## Prerequisites

- **Azure CLI** v2.50+ installed and logged in (`az login`)
- **Docker** installed for building images
- **Azure Subscription** with Contributor access
- **Azure OpenAI** resource provisioned with:
  - `gpt-4o-mini` deployment (chat)
  - `text-embedding-3-large` deployment (embeddings)

```bash
# Verify Azure CLI
az account show
az --version

# Verify Docker
docker --version
```

---

## 1. Azure Infrastructure (Bicep)

The entire infrastructure is defined in Bicep IaC under `infra/`.

### Dev Environment

```bash
# Option A: Use the Makefile
make azure-deploy-dev

# Option B: Direct CLI
./infra/scripts/deploy.sh dev
```

### Production Environment

```bash
make azure-deploy-prod
# or
./infra/scripts/deploy.sh prod
```

### Resources Provisioned

| Resource | Dev (B1ms) | Prod |
|----------|-----------|------|
| Resource Group | `rg-investorinsights-dev` | `rg-investorinsights-prod` |
| PostgreSQL Flexible Server | Burstable B1ms, 32GB | GeneralPurpose D2s, 128GB |
| Azure Container Registry | Basic | Standard |
| Container Apps Environment | Shared | Dedicated |
| Key Vault | Standard | Standard |
| Storage Account (Blob) | LRS | GRS |
| Azure OpenAI | Shared | Dedicated |
| Log Analytics Workspace | — | — |
| Application Insights | — | — |

### Bicep Parameters

Edit parameter files before deployment:

- `infra/parameters/dev.bicepparam` — Budget-optimized ($50/mo target)
- `infra/parameters/prod.bicepparam` — Full production config

Key parameters to set:
```
dbAdminLogin     = 'analyst'
dbAdminPassword  = '<strong-password>'
apiAuthKey       = '<generated-api-key>'
```

---

## 2. Seed Key Vault Secrets

After infrastructure is deployed, populate Key Vault with application secrets:

```bash
make azure-seed-keyvault
# or
./infra/scripts/seed-keyvault.sh dev
```

This stores the following secrets:
- `api-key` — API authentication key
- `db-password` — PostgreSQL password
- `azure-openai-api-key` — Azure OpenAI key
- `azure-openai-endpoint` — Azure OpenAI endpoint URL
- `azure-storage-connection-string` — Blob Storage connection

Container Apps are configured to reference these secrets from Key Vault.

---

## 3. Database Migration

Run Alembic migrations against the Azure PostgreSQL instance:

```bash
# Via Container Apps exec
make azure-migrate

# Or directly
az containerapp exec --name api \
    --resource-group rg-investorinsights-dev \
    --command "alembic upgrade head"
```

### Seed Default Data

```bash
az containerapp exec --name api \
    --resource-group rg-investorinsights-dev \
    --command "python -m app.scripts.seed_defaults"
```

---

## 4. Build & Push Docker Images

```bash
# Set your ACR name
export ACR_NAME=investorinsightsacr

# Login to ACR
az acr login --name $ACR_NAME

# Build and push (Makefile)
make azure-build-push

# Or manually:
docker build -t $ACR_NAME.azurecr.io/investorinsights-api:latest ./backend
docker build -t $ACR_NAME.azurecr.io/investorinsights-frontend:latest ./frontend
docker push $ACR_NAME.azurecr.io/investorinsights-api:latest
docker push $ACR_NAME.azurecr.io/investorinsights-frontend:latest
```

### Frontend Build Args

The frontend uses build-time environment variables. Pass them during Docker build:

```bash
docker build \
    --build-arg NEXT_PUBLIC_API_URL=https://api.investorinsights.example.com \
    --build-arg NEXT_PUBLIC_API_KEY=your-api-key \
    --build-arg NEXT_PUBLIC_LLM_MODEL=gpt-4o-mini \
    -t $ACR_NAME.azurecr.io/investorinsights-frontend:latest \
    ./frontend
```

---

## 5. Deploy Container Apps

```bash
make azure-deploy-apps

# Or manually update each container app:
ENV=dev
ACR_NAME=investorinsightsacr
RG=rg-investorinsights-$ENV

# API server
az containerapp update --name api \
    --resource-group $RG \
    --image $ACR_NAME.azurecr.io/investorinsights-api:latest

# Celery worker
az containerapp update --name worker \
    --resource-group $RG \
    --image $ACR_NAME.azurecr.io/investorinsights-api:latest

# Frontend
az containerapp update --name frontend \
    --resource-group $RG \
    --image $ACR_NAME.azurecr.io/investorinsights-frontend:latest
```

---

## 6. Verification

### Health Check

```bash
API_URL=$(az containerapp show --name api --resource-group $RG \
    --query properties.configuration.ingress.fqdn -o tsv)

curl -s https://$API_URL/api/v1/health | jq .
```

Expected:
```json
{
  "status": "healthy",
  "database": "connected",
  "version": "1.0.0"
}
```

### API Test

```bash
# List companies (should return empty initially)
curl -s -H "X-API-Key: $API_KEY" \
    https://$API_URL/api/v1/companies | jq .
```

### Frontend

```bash
FRONTEND_URL=$(az containerapp show --name frontend --resource-group $RG \
    --query properties.configuration.ingress.fqdn -o tsv)

echo "Frontend: https://$FRONTEND_URL"
# Open in browser
```

### Logs

```bash
# Stream API logs
make azure-logs

# Or
az containerapp logs show --name api --resource-group $RG --follow
```

---

## 7. Updating

### Deploy New Code

```bash
# 1. Build new images
make azure-build-push TAG=v1.1.0

# 2. Deploy
make azure-deploy-apps TAG=v1.1.0
```

### Run New Migrations

```bash
make azure-migrate
```

### Update Environment Variables

```bash
az containerapp update --name api \
    --resource-group $RG \
    --set-env-vars "LLM_MODEL=gpt-4o-mini" "RAG_TOP_K=15"
```

---

## 8. Teardown

### Scale to Zero (Pause — Preserves Data)

```bash
az containerapp update --name api --resource-group $RG \
    --min-replicas 0 --max-replicas 0
az containerapp update --name worker --resource-group $RG \
    --min-replicas 0 --max-replicas 0
az containerapp update --name frontend --resource-group $RG \
    --min-replicas 0 --max-replicas 0
```

### Full Destroy (⚠️ Irreversible)

```bash
make azure-destroy ENV=dev
# or
./infra/scripts/destroy.sh dev
```

---

## Architecture Overview

```
                    Internet
                       │
              ┌────────▼────────┐
              │  Azure Front    │
              │  Door / Ingress │
              └────────┬────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
  ┌─────▼─────┐ ┌─────▼─────┐ ┌─────▼─────┐
  │ Frontend  │ │   API     │ │  Worker   │
  │ Container │ │ Container │ │ Container │
  │ (Next.js) │ │ (FastAPI) │ │ (Celery)  │
  └───────────┘ └─────┬─────┘ └─────┬─────┘
                      │             │
       ┌──────────────┼─────────────┤
       │              │             │
  ┌────▼────┐  ┌──────▼──┐  ┌──────▼──────┐
  │PostgreSQL│  │  Redis  │  │ Azure Blob  │
  │ Flex Svr │  │Container│  │   Storage   │
  └─────────┘  └─────────┘  └─────────────┘
       │
  ┌────▼────┐  ┌──────────┐  ┌─────────────┐
  │ Qdrant  │  │Azure     │  │ App Insights│
  │Container│  │OpenAI    │  │ + Log Anlytx│
  └─────────┘  └──────────┘  └─────────────┘
```

---

## Cost Estimates

### Dev Environment (Target: ≤ $50/month)

| Resource | Estimated Cost |
|----------|---------------|
| PostgreSQL B1ms | ~$13/mo |
| Container Apps (3×0.5 vCPU) | ~$10-15/mo |
| Azure OpenAI (usage) | ~$5-15/mo |
| Container Registry (Basic) | ~$5/mo |
| Blob Storage (LRS) | ~$1/mo |
| Qdrant + Redis Containers | ~$5-8/mo |
| **Total** | **~$40-55/mo** |

See `docs/runbooks/budget-breach.md` for cost reduction procedures if budget is at risk.
