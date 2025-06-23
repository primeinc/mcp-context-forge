targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('Name of the environment that can be used as part of naming resource convention')
param environmentName string

@minLength(1)
@description('Primary location for all resources')
param location string

@description('Flag to deploy sample data')
param deploymentSampleData bool = false

// Optional parameters
param apiContainerAppName string = ''
param webContainerAppName string = ''
param containerAppsEnvironmentName string = ''
param containerRegistryName string = ''
param keyVaultName string = ''
param logAnalyticsName string = ''
param resourceGroupName string = ''

var abbrs = loadJsonContent('./abbreviations.json')
var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))
var tags = {
  'azd-env-name': environmentName
  'app-name': 'mcp-context-forge'
}

resource rg 'Microsoft.Resources/resourceGroups@2022-09-01' = {
  name: !empty(resourceGroupName) ? resourceGroupName : '${abbrs.resourcesResourceGroups}${environmentName}'
  location: location
  tags: tags
}

module monitoring './shared/monitoring.bicep' = {
  name: 'monitoring'
  scope: rg
  params: {
    location: location
    tags: tags
    logAnalyticsName: !empty(logAnalyticsName) ? logAnalyticsName : '${abbrs.operationalInsightsWorkspaces}${resourceToken}'
  }
}

module keyVault './shared/keyvault.bicep' = {
  name: 'keyvault'
  scope: rg
  params: {
    location: location
    tags: tags
    name: !empty(keyVaultName) ? keyVaultName : '${abbrs.keyVaultVaults}${resourceToken}'
    principalId: containerApps.outputs.API_IDENTITY_PRINCIPAL_ID
  }
}

module containerRegistry './shared/registry.bicep' = {
  name: 'registry'
  scope: rg
  params: {
    location: location
    tags: tags
    name: !empty(containerRegistryName) ? containerRegistryName : '${abbrs.containerRegistryRegistries}${resourceToken}'
  }
}

module containerApps './app/app.bicep' = {
  name: 'container-apps'
  scope: rg
  params: {
    location: location
    tags: tags
    containerAppsEnvironmentName: !empty(containerAppsEnvironmentName) ? containerAppsEnvironmentName : '${abbrs.appManagedEnvironments}${resourceToken}'
    containerRegistryName: containerRegistry.outputs.name
    keyVaultName: keyVault.outputs.name
    logAnalyticsWorkspaceName: monitoring.outputs.logAnalyticsWorkspaceName
    apiContainerAppName: !empty(apiContainerAppName) ? apiContainerAppName : '${abbrs.appContainerApps}api-${resourceToken}'
    webContainerAppName: !empty(webContainerAppName) ? webContainerAppName : '${abbrs.appContainerApps}web-${resourceToken}'
  }
}

module azureAd './shared/azuread.bicep' = {
  name: 'azuread'
  params: {
    environmentName: environmentName
    apiAppName: 'mcp-context-forge-api-${environmentName}'
    webAppName: 'mcp-context-forge-web-${environmentName}'
    apiBaseUrl: 'https://${containerApps.outputs.API_FQDN}'
    webBaseUrl: 'https://${containerApps.outputs.WEB_FQDN}'
    keyVaultName: keyVault.outputs.name
    resourceGroupName: rg.name
  }
}

// Store the API client secret in Key Vault
module apiSecretStore './shared/keyvault-secret.bicep' = {
  name: 'api-secret-store'
  scope: rg
  params: {
    keyVaultName: keyVault.outputs.name
    secretName: 'api-client-secret'
    secretValue: azureAd.outputs.apiClientSecret
  }
  dependsOn: [
    azureAd
  ]
}

// Outputs
output AZURE_LOCATION string = location
output AZURE_TENANT_ID string = tenant().tenantId
output AZURE_RESOURCE_GROUP string = rg.name

output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerRegistry.outputs.loginServer
output AZURE_CONTAINER_REGISTRY_NAME string = containerRegistry.outputs.name

output AZURE_KEY_VAULT_NAME string = keyVault.outputs.name
output AZURE_KEY_VAULT_ENDPOINT string = keyVault.outputs.endpoint

output API_BASE_URL string = 'https://${containerApps.outputs.API_FQDN}'
output WEB_BASE_URL string = 'https://${containerApps.outputs.WEB_FQDN}'

output AZURE_API_CLIENT_ID string = azureAd.outputs.apiClientId
output AZURE_WEB_CLIENT_ID string = azureAd.outputs.webClientId
output AZURE_AUTHORITY_HOST string = 'https://login.microsoftonline.com'
output API_AUDIENCE string = azureAd.outputs.apiApplicationIdUri

output API_IDENTITY_PRINCIPAL_ID string = containerApps.outputs.API_IDENTITY_PRINCIPAL_ID
output WEB_IDENTITY_PRINCIPAL_ID string = containerApps.outputs.WEB_IDENTITY_PRINCIPAL_ID