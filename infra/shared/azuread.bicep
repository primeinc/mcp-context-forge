// Azure AD App Registrations using Azure CLI deployment scripts
// Note: Microsoft.Graph provider is in preview and syntax may vary
// This approach uses deployment scripts for reliable app registration creation

param environmentName string
param apiAppName string
param webAppName string
param apiBaseUrl string
param webBaseUrl string
param keyVaultName string
param resourceGroupName string

// Deployment script for Azure AD app registrations
resource appRegistrationScript 'Microsoft.Resources/deploymentScripts@2023-08-01' = {
  name: 'create-ad-apps-${environmentName}'
  location: resourceGroup().location
  kind: 'AzureCLI'
  properties: {
    azCliVersion: '2.50.0'
    timeout: 'PT10M'
    retentionInterval: 'PT1H'
    environmentVariables: [
      {
        name: 'API_APP_NAME'
        value: apiAppName
      }
      {
        name: 'WEB_APP_NAME'
        value: webAppName
      }
      {
        name: 'API_BASE_URL'
        value: apiBaseUrl
      }
      {
        name: 'WEB_BASE_URL'
        value: webBaseUrl
      }
    ]
    scriptContent: '''
      set -e
      
      echo "Creating API app registration..."
      # Create API app registration
      API_APP=$(az ad app create \
        --display-name "$API_APP_NAME" \
        --identifier-uris "api://$API_APP_NAME" \
        --sign-in-audience AzureADMyOrg \
        --web-redirect-uris "$API_BASE_URL/auth/callback" \
        --required-resource-accesses '[{
          "resourceAppId": "00000003-0000-0000-c000-000000000000",
          "resourceAccess": [{
            "id": "e1fe6dd8-ba31-4d61-89e7-88639da4683d",
            "type": "Scope"
          }]
        }]' \
        --app-roles '[{
          "allowedMemberTypes": ["User", "Application"],
          "description": "Grants full administrative access to the MCP Gateway",
          "displayName": "Gateway.Admin",
          "id": "'$(uuidgen)'",
          "isEnabled": true,
          "value": "Gateway.Admin"
        }, {
          "allowedMemberTypes": ["User", "Application"],
          "description": "Grants user access to the MCP Gateway", 
          "displayName": "Gateway.User",
          "id": "'$(uuidgen)'",
          "isEnabled": true,
          "value": "Gateway.User"
        }]' \
        --query appId -o tsv)
      
      echo "API App ID: $API_APP"
      
      # Create service principal for API app
      az ad sp create --id $API_APP
      
      # Create API app secret
      API_SECRET=$(az ad app credential reset --id $API_APP --query password -o tsv)
      
      echo "Creating Web app registration..."
      # Create Web app registration  
      WEB_APP=$(az ad app create \
        --display-name "$WEB_APP_NAME" \
        --sign-in-audience AzureADMyOrg \
        --spa-redirect-uris "$WEB_BASE_URL/auth/callback" "$WEB_BASE_URL/" \
        --required-resource-accesses '[{
          "resourceAppId": "'$API_APP'",
          "resourceAccess": [{
            "id": "00000000-0000-0000-0000-000000000001",
            "type": "Scope"
          }]
        }, {
          "resourceAppId": "00000003-0000-0000-c000-000000000000",
          "resourceAccess": [{
            "id": "e1fe6dd8-ba31-4d61-89e7-88639da4683d",
            "type": "Scope"
          }]
        }]' \
        --query appId -o tsv)
      
      echo "Web App ID: $WEB_APP"
      
      # Create service principal for Web app
      az ad sp create --id $WEB_APP
      
      # Output results
      echo "{
        \"apiClientId\": \"$API_APP\",
        \"webClientId\": \"$WEB_APP\",
        \"apiApplicationIdUri\": \"api://$API_APP_NAME\",
        \"apiClientSecret\": \"$API_SECRET\"
      }" > $AZ_SCRIPTS_OUTPUT_PATH
    '''
  }
  identity: {
    type: 'SystemAssigned'
  }
}

// Grant permissions to the deployment script identity
resource scriptRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: resourceGroup()
  name: guid(resourceGroup().id, appRegistrationScript.id, 'Application Administrator')
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '9b895d92-2cd3-44c7-9d02-a6ac2d5ea5c3') // Application Administrator
    principalId: appRegistrationScript.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

output apiClientId string = appRegistrationScript.properties.outputs.apiClientId
output apiApplicationIdUri string = appRegistrationScript.properties.outputs.apiApplicationIdUri
output webClientId string = appRegistrationScript.properties.outputs.webClientId
output apiClientSecret string = appRegistrationScript.properties.outputs.apiClientSecret