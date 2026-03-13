// ============================================================
// Dev environment parameters — budget-optimised (≤ $50/month)
// No VNet, B1ms PostgreSQL, container Redis, scale-to-zero
// ============================================================
using '../main.bicep'

param environment = 'dev'
param location = 'eastus2'
param projectName = 'investorinsights'

// ── Database (Burstable B1ms — ~$13/month) ──────────────────────
param dbAdminLogin = readEnvironmentVariable('DB_ADMIN_LOGIN', 'analyst')
param dbAdminPassword = readEnvironmentVariable('DB_ADMIN_PASSWORD')
param dbSkuName = 'Standard_B1ms'
param dbSkuTier = 'Burstable'
param dbStorageSizeGB = 32
param dbBackupRetentionDays = 7

// ── Auth ────────────────────────────────────────────────────────
param apiAuthKey = readEnvironmentVariable('API_AUTH_KEY')

// ── SEC EDGAR ───────────────────────────────────────────────────
param secEdgarUserAgent = 'InvestorInsights/1.0 (admin@investorinsights.dev)'

// ── Networking (disabled for dev — saves ~$40/month) ────────────
param enableVnet = false

// ── Redis (container in dev, not managed — saves ~$15/month) ────
param enableManagedRedis = false

// ── Container Registry (Basic — ~$5/month) ──────────────────────
param acrSku = 'Basic'

// ── Azure OpenAI (gpt-4o-mini for dev — ~10x cheaper) ──────────
param openaiChatDeployment = 'gpt-4o-mini'
param openaiChatModel = 'gpt-4o-mini'
param openaiEmbeddingDeployment = 'text-embedding-3-large'

// ── Container Apps (scale-to-zero for all — consumption only) ───
param apiMinReplicas = 0
param apiMaxReplicas = 1
param workerMinReplicas = 0
param workerMaxReplicas = 2
param frontendMinReplicas = 0
param frontendMaxReplicas = 1
param qdrantMinReplicas = 0
param qdrantMaxReplicas = 1
