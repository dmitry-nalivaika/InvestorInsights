// Azure Key Vault module
param projectName string
param environment string
param location string
param tags object

@secure()
param dbConnectionString string
@secure()
param blobStorageConnection string
@secure()
param openaiApiKey string
param openaiEndpoint string
@secure()
param apiAuthKey string
param secEdgarUserAgent string
@secure()
param redisConnectionString string

var keyVaultName = take('kv-${projectName}-${environment}', 24)

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  tags: tags
  properties: {
    tenantId: subscription().tenantId
    sku: {
      family: 'A'
      name: 'standard'
    }
    enabledForDeployment: false
    enabledForTemplateDeployment: true
    enabledForDiskEncryption: false
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      defaultAction: 'Allow'
    }
  }
}

// ── Secrets ─────────────────────────────────────────────────────

resource secretDbConnection 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'db-connection-string'
  properties: {
    value: dbConnectionString
  }
}

resource secretBlobStorage 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'blob-storage-connection'
  properties: {
    value: blobStorageConnection
  }
}

resource secretOpenaiApiKey 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'azure-openai-api-key'
  properties: {
    value: openaiApiKey
  }
}

resource secretOpenaiEndpoint 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'azure-openai-endpoint'
  properties: {
    value: openaiEndpoint
  }
}

resource secretApiAuthKey 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'api-auth-key'
  properties: {
    value: apiAuthKey
  }
}

resource secretSecEdgarUserAgent 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'sec-edgar-user-agent'
  properties: {
    value: secEdgarUserAgent
  }
}

resource secretRedisConnection 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = if (!empty(redisConnectionString)) {
  parent: keyVault
  name: 'redis-connection-string'
  properties: {
    value: redisConnectionString
  }
}

output name string = keyVault.name
output uri string = keyVault.properties.vaultUri
