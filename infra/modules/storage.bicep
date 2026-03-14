// Azure Blob Storage module
@minLength(3)
param projectName string
@minLength(2)
param environment string
param location string
param tags object

// Storage account names: 3-24 lowercase alphanumeric only
var storageAccountName = take('st${replace(projectName, '-', '')}${environment}', 24)
var storageSku = environment == 'prod' ? 'Standard_ZRS' : 'Standard_LRS'

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: {
    name: storageSku
  }
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    allowSharedKeyAccess: true
    networkAcls: {
      defaultAction: 'Allow'
    }
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storageAccount
  name: 'default'
  properties: {
    deleteRetentionPolicy: {
      enabled: environment == 'prod'
      days: environment == 'prod' ? 14 : 1
    }
  }
}

// Filing documents container
resource filingsContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'filings'
  properties: {
    publicAccess: 'None'
  }
}

// Exports container
resource exportsContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'exports'
  properties: {
    publicAccess: 'None'
  }
}

output accountName string = storageAccount.name
// Key Vault stores the secret; this output is only consumed by the keyVault module in the same deployment
#disable-next-line outputs-should-not-contain-secrets
output connectionString string = 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};AccountKey=${storageAccount.listKeys().keys[0].value};EndpointSuffix=${az.environment().suffixes.storage}'
output blobEndpoint string = storageAccount.properties.primaryEndpoints.blob
