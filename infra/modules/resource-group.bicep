// Resource Group module
targetScope = 'subscription'

param name string
param location string
param tags object

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: name
  location: location
  tags: tags
}

output name string = rg.name
output id string = rg.id
