// ============================================================
// Prod environment parameters — full production configuration
// VNet + private endpoints, managed Redis, larger SKUs, HA
// ============================================================
using '../main.bicep'

param environment = 'prod'
param location = 'eastus2'
param projectName = 'investorinsights'

// ── Database (General Purpose D2ds_v5 — 2 vCore, 8 GB) ─────────
param dbAdminLogin = readEnvironmentVariable('DB_ADMIN_LOGIN', 'analyst')
param dbAdminPassword = readEnvironmentVariable('DB_ADMIN_PASSWORD', 'DEPLOY_TIME_SECRET')
param dbSkuName = 'Standard_D2ds_v5'
param dbSkuTier = 'GeneralPurpose'
param dbStorageSizeGB = 128
param dbBackupRetentionDays = 35

// ── Auth ────────────────────────────────────────────────────────
param apiAuthKey = readEnvironmentVariable('API_AUTH_KEY', 'DEPLOY_TIME_SECRET')

// ── SEC EDGAR ───────────────────────────────────────────────────
param secEdgarUserAgent = readEnvironmentVariable('SEC_EDGAR_USER_AGENT', 'InvestorInsights/1.0 (admin@investorinsights.dev)')

// ── Networking (full VNet with private endpoints) ───────────────
param enableVnet = true

// ── Redis (Azure Cache for Redis Standard C1 — 1 GB) ───────────
param enableManagedRedis = true

// ── Container Registry (Standard — geo-replication capable) ─────
param acrSku = 'Standard'

// ── Azure OpenAI (gpt-4o for prod — better reasoning) ──────────
param openaiChatDeployment = 'gpt-4o'
param openaiChatModel = 'gpt-4o'
param openaiEmbeddingDeployment = 'text-embedding-3-large'

// ── Container Apps (always-on, higher scaling) ──────────────────
param apiMinReplicas = 1
param apiMaxReplicas = 5
param workerMinReplicas = 1
param workerMaxReplicas = 5
param frontendMinReplicas = 1
param frontendMaxReplicas = 3
param qdrantMinReplicas = 1
param qdrantMaxReplicas = 1
