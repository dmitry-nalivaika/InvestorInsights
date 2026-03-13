// Azure Cache for Redis module (prod only)
param projectName string
param environment string
param location string
param tags object

var redisName = 'redis-${projectName}-${environment}'

resource redis 'Microsoft.Cache/redis@2024-03-01' = {
  name: redisName
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'Standard'
      family: 'C'
      capacity: 1 // C1 = 1 GB
    }
    enableNonSslPort: false
    minimumTlsVersion: '1.2'
    redisConfiguration: {
      'maxmemory-policy': 'allkeys-lru'
    }
  }
}

output connectionString string = '${redisName}.redis.cache.windows.net:6380,password=${redis.listKeys().primaryKey},ssl=True,abortConnect=False'
output hostName string = redis.properties.hostName
output name string = redis.name
