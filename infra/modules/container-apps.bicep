// Container Apps Environment + All Apps module
param projectName string
param environment string
param location string
param tags object
param logAnalyticsWorkspaceId string
@secure()
param appInsightsConnectionString string
param acrLoginServer string
param keyVaultName string
param enableManagedRedis bool

param apiMinReplicas int
param apiMaxReplicas int
param workerMinReplicas int
param workerMaxReplicas int
param frontendMinReplicas int
param frontendMaxReplicas int
param qdrantMinReplicas int
param qdrantMaxReplicas int

@description('Azure Files storage account name for Qdrant persistence (configure post-deploy)')
param qdrantStorageAccountName string = 'placeholder'
@description('Azure Files storage account key for Qdrant persistence (configure post-deploy)')
@secure()
param qdrantStorageAccountKey string = ''

var envName = 'cae-${projectName}-${environment}'
var isDev = environment == 'dev'

// CPU/memory per environment
var apiCpu = isDev ? '0.25' : '1.0'
var apiMemory = isDev ? '0.5Gi' : '2Gi'
var workerCpu = isDev ? '0.5' : '2.0'
var workerMemory = isDev ? '1Gi' : '4Gi'
var frontendCpu = isDev ? '0.25' : '0.5'
var frontendMemory = isDev ? '0.5Gi' : '1Gi'
var qdrantCpu = isDev ? '0.25' : '1.0'
var qdrantMemory = isDev ? '1Gi' : '4Gi'

// ── Container Apps Environment ──────────────────────────────────
resource containerAppsEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: envName
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: reference(logAnalyticsWorkspaceId, '2023-09-01').customerId
        sharedKey: listKeys(logAnalyticsWorkspaceId, '2023-09-01').primarySharedKey
      }
    }
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
  }
}

// ── Azure Files volume for Qdrant persistence ───────────────────
// Note: defaults are placeholders — configure with real values post-deploy or via Key Vault.
resource qdrantStorage 'Microsoft.App/managedEnvironments/storages@2024-03-01' = {
  parent: containerAppsEnv
  name: 'qdrantstorage'
  properties: {
    azureFile: {
      accountName: qdrantStorageAccountName
      accountKey: qdrantStorageAccountKey
      shareName: 'qdrant-data'
      accessMode: 'ReadWrite'
    }
  }
}

// ── API Container App ───────────────────────────────────────────
resource apiApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'ca-${projectName}-api-${environment}'
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: containerAppsEnv.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        transport: 'http'
        corsPolicy: {
          allowedOrigins: ['*']
          allowedMethods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']
          allowedHeaders: ['*']
        }
      }
      registries: [
        {
          server: acrLoginServer
          // Uses managed identity or admin credentials configured at deploy
        }
      ]
      secrets: [
        {
          name: 'appinsights-connection-string'
          value: appInsightsConnectionString
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'api'
          image: '${acrLoginServer}/investorinsights-api:latest'
          resources: {
            cpu: json(apiCpu)
            memory: apiMemory
          }
          env: [
            { name: 'APP_ENV', value: environment }
            { name: 'APP_NAME', value: projectName }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', secretRef: 'appinsights-connection-string' }
            { name: 'OTEL_SERVICE_NAME', value: 'investorinsights-api' }
          ]
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/api/v1/health'
                port: 8000
              }
              periodSeconds: 30
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/api/v1/health'
                port: 8000
              }
              initialDelaySeconds: 10
              periodSeconds: 10
            }
          ]
        }
      ]
      scale: {
        minReplicas: apiMinReplicas
        maxReplicas: apiMaxReplicas
        rules: [
          {
            name: 'http-scaling'
            http: {
              metadata: {
                concurrentRequests: '50'
              }
            }
          }
        ]
      }
    }
  }
}

// ── Worker Container App ────────────────────────────────────────
resource workerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'ca-${projectName}-worker-${environment}'
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: containerAppsEnv.id
    configuration: {
      registries: [
        {
          server: acrLoginServer
        }
      ]
      secrets: [
        {
          name: 'appinsights-connection-string'
          value: appInsightsConnectionString
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'worker'
          image: '${acrLoginServer}/investorinsights-api:latest'
          command: [
            'celery'
            '-A'
            'app.worker.celery_app'
            'worker'
            '--loglevel=info'
            '--concurrency=${isDev ? '2' : '4'}'
            '--queues=ingestion,analysis,sec_fetch'
            '--max-tasks-per-child=50'
          ]
          resources: {
            cpu: json(workerCpu)
            memory: workerMemory
          }
          env: [
            { name: 'APP_ENV', value: environment }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', secretRef: 'appinsights-connection-string' }
            { name: 'OTEL_SERVICE_NAME', value: 'investorinsights-worker' }
          ]
        }
      ]
      scale: {
        minReplicas: workerMinReplicas
        maxReplicas: workerMaxReplicas
      }
    }
  }
}

// ── Frontend Container App ──────────────────────────────────────
resource frontendApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'ca-${projectName}-frontend-${environment}'
  location: location
  tags: tags
  properties: {
    managedEnvironmentId: containerAppsEnv.id
    configuration: {
      ingress: {
        external: true
        targetPort: 3000
        transport: 'http'
      }
      registries: [
        {
          server: acrLoginServer
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'frontend'
          image: '${acrLoginServer}/investorinsights-frontend:latest'
          resources: {
            cpu: json(frontendCpu)
            memory: frontendMemory
          }
          env: [
            { name: 'NEXT_PUBLIC_API_URL', value: 'https://ca-${projectName}-api-${environment}.${containerAppsEnv.properties.defaultDomain}' }
            { name: 'NEXT_PUBLIC_APP_NAME', value: 'InvestorInsights' }
          ]
        }
      ]
      scale: {
        minReplicas: frontendMinReplicas
        maxReplicas: frontendMaxReplicas
      }
    }
  }
}

// ── Qdrant Container App ────────────────────────────────────────
resource qdrantApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'ca-${projectName}-qdrant-${environment}'
  location: location
  tags: tags
  properties: {
    managedEnvironmentId: containerAppsEnv.id
    configuration: {
      ingress: {
        external: false // Internal only
        targetPort: 6333
        transport: 'http'
      }
    }
    template: {
      containers: [
        {
          name: 'qdrant'
          image: 'qdrant/qdrant:v1.9.7'
          resources: {
            cpu: json(qdrantCpu)
            memory: qdrantMemory
          }
          volumeMounts: [
            {
              volumeName: 'qdrant-data'
              mountPath: '/qdrant/storage'
            }
          ]
        }
      ]
      volumes: [
        {
          name: 'qdrant-data'
          storageName: qdrantStorage.name
          storageType: 'AzureFile'
        }
      ]
      scale: {
        minReplicas: qdrantMinReplicas
        maxReplicas: qdrantMaxReplicas
      }
    }
  }
}

// ── Redis Container App (dev only — prod uses Azure Cache) ──────
resource redisApp 'Microsoft.App/containerApps@2024-03-01' = if (!enableManagedRedis) {
  name: 'ca-${projectName}-redis-${environment}'
  location: location
  tags: tags
  properties: {
    managedEnvironmentId: containerAppsEnv.id
    configuration: {
      ingress: {
        external: false
        targetPort: 6379
        transport: 'tcp'
      }
    }
    template: {
      containers: [
        {
          name: 'redis'
          image: 'redis:7-alpine'
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          command: ['redis-server', '--save', '60', '1', '--loglevel', 'warning']
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 1
      }
    }
  }
}

// ── Key Vault RBAC: grant API + Worker access to secrets ────────
// "Key Vault Secrets User" role = 4633458b-17de-408a-b874-0445c86b69e6
var keyVaultSecretsUserRoleId = '4633458b-17de-408a-b874-0445c86b69e6'

resource keyVaultRef 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}

resource apiKeyVaultAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVaultRef.id, apiApp.id, keyVaultSecretsUserRoleId)
  scope: keyVaultRef
  properties: {
    principalId: apiApp.identity.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', keyVaultSecretsUserRoleId)
    principalType: 'ServicePrincipal'
  }
}

resource workerKeyVaultAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVaultRef.id, workerApp.id, keyVaultSecretsUserRoleId)
  scope: keyVaultRef
  properties: {
    principalId: workerApp.identity.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', keyVaultSecretsUserRoleId)
    principalType: 'ServicePrincipal'
  }
}

output environmentName string = containerAppsEnv.name
output apiFqdn string = apiApp.properties.configuration.ingress.fqdn
output frontendFqdn string = frontendApp.properties.configuration.ingress.fqdn
