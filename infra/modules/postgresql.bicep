// Azure Database for PostgreSQL Flexible Server module
param projectName string
param environment string
param location string
param tags object

@secure()
param adminLogin string
@secure()
param adminPassword string

@description('SKU name (e.g., Standard_B1ms, Standard_D2ds_v5)')
param skuName string

@allowed(['Burstable', 'GeneralPurpose', 'MemoryOptimized'])
param skuTier string

param storageSizeGB int
param backupRetentionDays int
param enableVnet bool
param subnetId string

var serverName = 'psql-${projectName}-${environment}'

resource postgresServer 'Microsoft.DBforPostgreSQL/flexibleServers@2023-12-01-preview' = {
  name: serverName
  location: location
  tags: tags
  sku: {
    name: skuName
    tier: skuTier
  }
  properties: {
    version: '16'
    administratorLogin: adminLogin
    administratorLoginPassword: adminPassword
    storage: {
      storageSizeGB: storageSizeGB
      autoGrow: 'Disabled'
    }
    backup: {
      backupRetentionDays: backupRetentionDays
      geoRedundantBackup: environment == 'prod' ? 'Enabled' : 'Disabled'
    }
    highAvailability: {
      mode: 'Disabled'
    }
    network: enableVnet ? {
      delegatedSubnetResourceId: subnetId
    } : {}
  }
}

// Default database
resource database 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2023-12-01-preview' = {
  parent: postgresServer
  name: 'company_analysis'
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
}

// Extensions: uuid-ossp, pgcrypto
resource extensionUuid 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2023-12-01-preview' = {
  parent: postgresServer
  name: 'azure.extensions'
  properties: {
    value: 'UUID-OSSP,PGCRYPTO'
    source: 'user-override'
  }
}

// Allow Azure services (dev only — no VNet)
resource firewallAllowAzure 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2023-12-01-preview' = if (!enableVnet) {
  parent: postgresServer
  name: 'AllowAzureServices'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

output fqdn string = postgresServer.properties.fullyQualifiedDomainName
output serverName string = postgresServer.name
