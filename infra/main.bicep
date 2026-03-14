// ============================================================
// InvestorInsights — Main Bicep Orchestrator
// Deploys all Azure resources for the InvestorInsights platform.
// Usage:
//   az deployment sub create --location eastus2 \
//     --template-file infra/main.bicep \
//     --parameters infra/parameters/dev.bicepparam
// ============================================================

targetScope = 'subscription'

// ── Parameters ──────────────────────────────────────────────────
@description('Environment name (dev, staging, prod)')
@allowed(['dev', 'staging', 'prod'])
param environment string

@description('Azure region for all resources')
param location string = 'eastus2'

@description('Project name prefix for resource naming')
param projectName string = 'investorinsights'

@description('Administrator login for PostgreSQL')
@secure()
param dbAdminLogin string

@description('Administrator password for PostgreSQL')
@secure()
param dbAdminPassword string

@description('API authentication key for V1 auth')
@secure()
param apiAuthKey string

@description('SEC EDGAR User-Agent header value')
param secEdgarUserAgent string = 'InvestorInsights/1.0 (admin@investorinsights.dev)'

@description('Enable VNet with private endpoints (prod only)')
param enableVnet bool = false

@description('Enable Azure Cache for Redis (prod only, dev uses container)')
param enableManagedRedis bool = false

@description('PostgreSQL SKU name')
param dbSkuName string = 'Standard_B1ms'

@description('PostgreSQL SKU tier')
@allowed(['Burstable', 'GeneralPurpose', 'MemoryOptimized'])
param dbSkuTier string = 'Burstable'

@description('PostgreSQL storage size in GB')
param dbStorageSizeGB int = 32

@description('PostgreSQL backup retention days')
param dbBackupRetentionDays int = 7

@description('Azure Container Registry SKU')
@allowed(['Basic', 'Standard', 'Premium'])
param acrSku string = 'Basic'

@description('Azure OpenAI chat model deployment name')
param openaiChatDeployment string = 'gpt-4o-mini'

@description('Azure OpenAI chat model name')
param openaiChatModel string = 'gpt-4o-mini'

@description('Azure OpenAI embedding model deployment name')
param openaiEmbeddingDeployment string = 'text-embedding-3-large'

@description('Container Apps — API min replicas')
param apiMinReplicas int = 0

@description('Container Apps — API max replicas')
param apiMaxReplicas int = 1

@description('Container Apps — Worker min replicas')
param workerMinReplicas int = 0

@description('Container Apps — Worker max replicas')
param workerMaxReplicas int = 2

@description('Container Apps — Frontend min replicas')
param frontendMinReplicas int = 0

@description('Container Apps — Frontend max replicas')
param frontendMaxReplicas int = 1

@description('Container Apps — Qdrant min replicas')
param qdrantMinReplicas int = 0

@description('Container Apps — Qdrant max replicas')
param qdrantMaxReplicas int = 1

// ── Naming Convention ───────────────────────────────────────────
var resourceGroupName = 'rg-${projectName}-${environment}'
var tags = {
  project: projectName
  environment: environment
  managedBy: 'bicep'
}

// ── Resource Group ──────────────────────────────────────────────
module resourceGroup 'modules/resource-group.bicep' = {
  name: 'deploy-resource-group'
  params: {
    name: resourceGroupName
    location: location
    tags: tags
  }
}

// ── Log Analytics + Application Insights ────────────────────────
module logAnalytics 'modules/log-analytics.bicep' = {
  name: 'deploy-log-analytics'
  scope: az.resourceGroup(resourceGroupName)
  params: {
    projectName: projectName
    environment: environment
    location: location
    tags: tags
  }
  dependsOn: [resourceGroup]
}

module appInsights 'modules/app-insights.bicep' = {
  name: 'deploy-app-insights'
  scope: az.resourceGroup(resourceGroupName)
  params: {
    projectName: projectName
    environment: environment
    location: location
    tags: tags
    logAnalyticsWorkspaceId: logAnalytics.outputs.workspaceId
  }
}

// ── Networking (prod only) ──────────────────────────────────────
module networking 'modules/networking.bicep' = if (enableVnet) {
  name: 'deploy-networking'
  scope: az.resourceGroup(resourceGroupName)
  params: {
    projectName: projectName
    environment: environment
    location: location
    tags: tags
  }
  dependsOn: [resourceGroup]
}

// ── PostgreSQL ──────────────────────────────────────────────────
module postgresql 'modules/postgresql.bicep' = {
  name: 'deploy-postgresql'
  scope: az.resourceGroup(resourceGroupName)
  params: {
    projectName: projectName
    environment: environment
    location: location
    tags: tags
    adminLogin: dbAdminLogin
    adminPassword: dbAdminPassword
    skuName: dbSkuName
    skuTier: dbSkuTier
    storageSizeGB: dbStorageSizeGB
    backupRetentionDays: dbBackupRetentionDays
    enableVnet: enableVnet
    subnetId: enableVnet && networking != null ? networking!.outputs.postgresSubnetId : ''
  }
  dependsOn: [resourceGroup]
}

// ── Blob Storage ────────────────────────────────────────────────
module storage 'modules/storage.bicep' = {
  name: 'deploy-storage'
  scope: az.resourceGroup(resourceGroupName)
  params: {
    projectName: projectName
    environment: environment
    location: location
    tags: tags
  }
  dependsOn: [resourceGroup]
}

// ── Azure Cache for Redis (prod only) ───────────────────────────
module redis 'modules/redis.bicep' = if (enableManagedRedis) {
  name: 'deploy-redis'
  scope: az.resourceGroup(resourceGroupName)
  params: {
    projectName: projectName
    environment: environment
    location: location
    tags: tags
  }
  dependsOn: [resourceGroup]
}

// ── Azure OpenAI ────────────────────────────────────────────────
module openai 'modules/openai.bicep' = {
  name: 'deploy-openai'
  scope: az.resourceGroup(resourceGroupName)
  params: {
    projectName: projectName
    environment: environment
    location: location
    tags: tags
    chatDeploymentName: openaiChatDeployment
    chatModelName: openaiChatModel
    embeddingDeploymentName: openaiEmbeddingDeployment
  }
  dependsOn: [resourceGroup]
}

// ── Key Vault ───────────────────────────────────────────────────
module keyVault 'modules/key-vault.bicep' = {
  name: 'deploy-key-vault'
  scope: az.resourceGroup(resourceGroupName)
  params: {
    projectName: projectName
    environment: environment
    location: location
    tags: tags
    dbConnectionString: 'postgresql+asyncpg://${dbAdminLogin}:${dbAdminPassword}@${postgresql.outputs.fqdn}:5432/company_analysis'
    blobStorageConnection: storage.outputs.connectionString
    openaiApiKey: openai.outputs.apiKey
    openaiEndpoint: openai.outputs.endpoint
    apiAuthKey: apiAuthKey
    secEdgarUserAgent: secEdgarUserAgent
    redisConnectionString: enableManagedRedis && redis != null ? redis!.outputs.connectionString : ''
  }
}

// ── Container Registry ──────────────────────────────────────────
module containerRegistry 'modules/container-registry.bicep' = {
  name: 'deploy-container-registry'
  scope: az.resourceGroup(resourceGroupName)
  params: {
    projectName: projectName
    environment: environment
    location: location
    tags: tags
    sku: acrSku
  }
  dependsOn: [resourceGroup]
}

// ── Container Apps Environment + Apps ───────────────────────────
module containerApps 'modules/container-apps.bicep' = {
  name: 'deploy-container-apps'
  scope: az.resourceGroup(resourceGroupName)
  params: {
    projectName: projectName
    environment: environment
    location: location
    tags: tags
    logAnalyticsWorkspaceId: logAnalytics.outputs.workspaceId
    appInsightsConnectionString: appInsights.outputs.connectionString
    acrLoginServer: containerRegistry.outputs.loginServer
    keyVaultName: keyVault.outputs.name
    enableManagedRedis: enableManagedRedis
    apiMinReplicas: apiMinReplicas
    apiMaxReplicas: apiMaxReplicas
    workerMinReplicas: workerMinReplicas
    workerMaxReplicas: workerMaxReplicas
    frontendMinReplicas: frontendMinReplicas
    frontendMaxReplicas: frontendMaxReplicas
    qdrantMinReplicas: qdrantMinReplicas
    qdrantMaxReplicas: qdrantMaxReplicas
  }
}

// ── Outputs ─────────────────────────────────────────────────────
output resourceGroupName string = resourceGroupName
output postgresqlFqdn string = postgresql.outputs.fqdn
output storageAccountName string = storage.outputs.accountName
output acrLoginServer string = containerRegistry.outputs.loginServer
output keyVaultName string = keyVault.outputs.name
output appInsightsConnectionString string = appInsights.outputs.connectionString
output openaiEndpoint string = openai.outputs.endpoint
output containerAppsEnvironmentName string = containerApps.outputs.environmentName
