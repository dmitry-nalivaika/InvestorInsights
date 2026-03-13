// Log Analytics Workspace module
param projectName string
param environment string
param location string
param tags object

var workspaceName = 'law-${projectName}-${environment}'

resource workspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: workspaceName
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
    features: {
      enableLogAccessUsingOnlyResourcePermissions: true
    }
    workspaceCapping: {
      dailyQuotaGb: environment == 'dev' ? 1 : -1 // 1 GB cap for dev, unlimited for prod
    }
  }
}

output workspaceId string = workspace.id
output workspaceName string = workspace.name
