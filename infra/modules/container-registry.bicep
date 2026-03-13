// Azure Container Registry module
param projectName string
param environment string
param location string
param tags object

@allowed(['Basic', 'Standard', 'Premium'])
param sku string

var acrName = replace('acr${projectName}${environment}', '-', '')

resource acr 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' = {
  name: acrName
  location: location
  tags: tags
  sku: {
    name: sku
  }
  properties: {
    adminUserEnabled: true // Needed for Container Apps pull in dev
    publicNetworkAccess: 'Enabled'
  }
}

output loginServer string = acr.properties.loginServer
output name string = acr.name
