// Azure OpenAI Service module
param projectName string
param environment string
param location string
param tags object
param chatDeploymentName string
param chatModelName string
param embeddingDeploymentName string

var openaiName = 'oai-${projectName}-${environment}'

resource openai 'Microsoft.CognitiveServices/accounts@2024-04-01-preview' = {
  name: openaiName
  location: location
  tags: tags
  kind: 'OpenAI'
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: openaiName
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      defaultAction: 'Allow'
    }
  }
}

// Chat model deployment (gpt-4o-mini for dev, gpt-4o for prod)
resource chatDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-04-01-preview' = {
  parent: openai
  name: chatDeploymentName
  sku: {
    name: 'Standard'
    capacity: environment == 'dev' ? 10 : 30 // TPM in thousands
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: chatModelName
      version: '2024-07-18'
    }
    raiPolicyName: 'Microsoft.DefaultV2'
  }
}

// Embedding model deployment
resource embeddingDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-04-01-preview' = {
  parent: openai
  name: embeddingDeploymentName
  sku: {
    name: 'Standard'
    capacity: environment == 'dev' ? 10 : 30
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'text-embedding-3-large'
      version: '1'
    }
    raiPolicyName: 'Microsoft.DefaultV2'
  }
  dependsOn: [chatDeployment] // Serial deployment to avoid conflicts
}

output endpoint string = openai.properties.endpoint
// Key Vault stores the secret; this output is only consumed by the keyVault module in the same deployment
#disable-next-line outputs-should-not-contain-secrets
output apiKey string = openai.listKeys().key1
output name string = openai.name
