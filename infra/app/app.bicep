param location string
param tags object = {}

param containerAppsEnvironmentName string
param containerRegistryName string
param keyVaultName string
param logAnalyticsWorkspaceName string
param apiContainerAppName string
param webContainerAppName string

// Container Apps Environment
resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2023-05-01' = {
  name: containerAppsEnvironmentName
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsWorkspace.properties.customerId
        sharedKey: logAnalyticsWorkspace.listKeys().primarySharedKey
      }
    }
  }
}

resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2022-10-01' existing = {
  name: logAnalyticsWorkspaceName
}

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: containerRegistryName
}

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}

// Managed Identity for API
resource apiIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${apiContainerAppName}-identity'
  location: location
  tags: tags
}

// Managed Identity for Web
resource webIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${webContainerAppName}-identity'
  location: location
  tags: tags
}

// API Container App
resource apiContainerApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: apiContainerAppName
  location: location
  tags: union(tags, { 'azd-service-name': 'api' })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${apiIdentity.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppsEnvironment.id
    configuration: {
      ingress: {
        external: true
        targetPort: 4444
        allowInsecure: false
        traffic: [
          {
            weight: 100
            latestRevision: true
          }
        ]
      }
      registries: [
        {
          server: containerRegistry.properties.loginServer
          identity: apiIdentity.id
        }
      ]
      secrets: [
        {
          name: 'api-client-secret'
          keyVaultUrl: '${keyVault.properties.vaultUri}secrets/api-client-secret'
          identity: apiIdentity.id
        }
        {
          name: 'container-registry-password'
          value: containerRegistry.listCredentials().passwords[0].value
        }
      ]
    }
    template: {
      containers: [
        {
          image: 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
          name: 'api'
          env: [
            {
              name: 'HOST'
              value: '0.0.0.0'
            }
            {
              name: 'PORT'
              value: '4444'
            }
            {
              name: 'AUTH_TYPE'
              value: 'azure_ad'
            }
            {
              name: 'AZURE_CLIENT_ID'
              value: '#{AZURE_API_CLIENT_ID}#' // Will be set by deployment
            }
            {
              name: 'AZURE_CLIENT_SECRET'
              secretRef: 'api-client-secret'
            }
            {
              name: 'AZURE_TENANT_ID'
              value: '#{AZURE_TENANT_ID}#' // Will be set by deployment
            }
            {
              name: 'AZURE_AUTHORITY_HOST'
              value: 'https://login.microsoftonline.com'
            }
            {
              name: 'API_AUDIENCE'
              value: '#{API_AUDIENCE}#' // Will be set by deployment
            }
            {
              name: 'DATABASE_URL'
              value: 'sqlite:///./mcp.db'
            }
            {
              name: 'AZURE_KEY_VAULT_NAME'
              value: keyVaultName
            }
            {
              name: 'CORS_ENABLED'
              value: 'true'
            }
            {
              name: 'LOG_LEVEL'
              value: 'INFO'
            }
            {
              name: 'MCPGATEWAY_UI_ENABLED'
              value: 'false' // UI is separate container
            }
            {
              name: 'MCPGATEWAY_ADMIN_API_ENABLED'
              value: 'true'
            }
          ]
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 10
        rules: [
          {
            name: 'http-scaler'
            http: {
              metadata: {
                concurrentRequests: '100'
              }
            }
          }
        ]
      }
    }
  }
}

// Web Container App (Admin UI)
resource webContainerApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: webContainerAppName
  location: location
  tags: union(tags, { 'azd-service-name': 'web' })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${webIdentity.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppsEnvironment.id
    configuration: {
      ingress: {
        external: true
        targetPort: 80
        allowInsecure: false
        traffic: [
          {
            weight: 100
            latestRevision: true
          }
        ]
      }
      registries: [
        {
          server: containerRegistry.properties.loginServer
          identity: webIdentity.id
        }
      ]
      secrets: [
        {
          name: 'container-registry-password'
          value: containerRegistry.listCredentials().passwords[0].value
        }
      ]
    }
    template: {
      containers: [
        {
          image: 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
          name: 'web'
          env: [
            {
              name: 'AZURE_CLIENT_ID'
              value: '#{AZURE_WEB_CLIENT_ID}#' // Will be set by deployment
            }
            {
              name: 'AZURE_TENANT_ID'
              value: '#{AZURE_TENANT_ID}#' // Will be set by deployment
            }
            {
              name: 'AZURE_AUTHORITY_HOST'
              value: 'https://login.microsoftonline.com'
            }
            {
              name: 'API_BASE_URL'
              value: 'https://${apiContainerApp.properties.configuration.ingress.fqdn}'
            }
            {
              name: 'WEB_REDIRECT_URI'
              value: 'https://#{WEB_FQDN}#/auth/callback' // Will be set by deployment
            }
          ]
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 5
        rules: [
          {
            name: 'http-scaler'
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

output API_IDENTITY_PRINCIPAL_ID string = apiIdentity.properties.principalId
output WEB_IDENTITY_PRINCIPAL_ID string = webIdentity.properties.principalId
output API_NAME string = apiContainerApp.name
output WEB_NAME string = webContainerApp.name
output API_FQDN string = apiContainerApp.properties.configuration.ingress.fqdn
output WEB_FQDN string = webContainerApp.properties.configuration.ingress.fqdn
output CONTAINER_APPS_ENVIRONMENT_NAME string = containerAppsEnvironment.name
output CONTAINER_APPS_ENVIRONMENT_ID string = containerAppsEnvironment.id