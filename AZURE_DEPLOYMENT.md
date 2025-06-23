# Azure Deployment Guide for MCP Context Forge

This guide provides complete instructions for deploying MCP Context Forge to Azure using Azure Developer CLI (azd) with production-grade Azure AD authentication.

## Architecture

The deployment creates the following Azure resources:

### Core Infrastructure
- **Azure Container Apps Environment**: Serverless container hosting
- **Azure Container Registry**: Private container image storage
- **Azure Key Vault**: Secure secrets management
- **Azure Log Analytics**: Centralized logging and monitoring

### Applications
- **API Container App**: MCP Gateway API with Azure AD authentication
- **Web Container App**: Admin UI with MSAL authentication

### Azure AD Integration
- **API App Registration**: Backend API with scopes and roles
- **Web App Registration**: SPA client with appropriate permissions
- **Managed Identities**: Secure access to Key Vault and other Azure resources

## Prerequisites

1. **Azure Subscription**: Active Azure subscription with contributor access
2. **Azure Developer CLI**: [Install azd](https://docs.microsoft.com/en-us/azure/developer/azure-developer-cli/install-azd)
3. **Docker**: For building container images locally (optional for CI/CD)
4. **Azure CLI**: [Install Azure CLI](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli) (optional, for manual operations)

## Quick Deployment

### 1. Clone and Setup

```bash
git clone https://github.com/primeinc/mcp-context-forge.git
cd mcp-context-forge
```

### 2. Initialize Azure Developer CLI

```bash
azd init
# Select "Use code in the current directory"
# Environment name: e.g., "mcpforge-prod"
```

### 3. Deploy to Azure

```bash
# This will provision infrastructure and deploy applications
azd up

# Follow prompts for:
# - Azure subscription selection
# - Azure region selection
# - API client secret (auto-generated secure value recommended)
```

### 4. Access the Application

After deployment completes:

1. **API Endpoint**: `https://<api-app>.azurecontainerapps.io`
2. **Web UI**: `https://<web-app>.azurecontainerapps.io`
3. **Azure AD Apps**: Check Azure Portal > Azure Active Directory > App registrations

## Environment Variables

The deployment uses the following key environment variables:

### API Container App
- `AZURE_CLIENT_ID`: Azure AD API app client ID
- `AZURE_TENANT_ID`: Azure AD tenant ID
- `AZURE_CLIENT_SECRET`: API app client secret (from Key Vault)
- `API_AUDIENCE`: API application ID URI
- `AUTH_TYPE`: Set to `azure_ad`
- `AZURE_KEY_VAULT_NAME`: Key Vault name for secrets

### Web Container App
- `AZURE_CLIENT_ID`: Azure AD web app client ID
- `AZURE_TENANT_ID`: Azure AD tenant ID
- `API_BASE_URL`: Backend API URL
- `WEB_REDIRECT_URI`: OAuth redirect URI

## Authentication Flow

### 1. Web UI Authentication
1. User accesses the web application
2. MSAL.js redirects to Azure AD for authentication
3. User signs in with Azure AD credentials
4. Azure AD returns access token with appropriate scopes
5. Web app uses token to call API endpoints

### 2. API Authentication
1. API receives requests with Bearer token
2. `fastapi-azure-auth` validates token against Azure AD
3. Token claims determine user permissions (Gateway.Admin, Gateway.User)
4. API processes authenticated requests

### 3. Key Vault Access
1. Container Apps use Managed Identity
2. Key Vault grants access via RBAC (Key Vault Secrets User role)
3. Applications retrieve secrets without hardcoded credentials

## Configuration

### Azure AD App Registrations

#### API App Registration
```json
{
  "displayName": "mcp-context-forge-api-{environment}",
  "signInAudience": "AzureADMyOrg",
  "identifierUris": ["api://mcp-context-forge-api-{environment}"],
  "appRoles": [
    {
      "displayName": "Gateway.Admin",
      "value": "Gateway.Admin",
      "allowedMemberTypes": ["User", "Application"]
    },
    {
      "displayName": "Gateway.User", 
      "value": "Gateway.User",
      "allowedMemberTypes": ["User", "Application"]
    }
  ]
}
```

#### Web App Registration
```json
{
  "displayName": "mcp-context-forge-web-{environment}",
  "signInAudience": "AzureADMyOrg",
  "spa": {
    "redirectUris": [
      "https://{web-app-fqdn}/auth/callback",
      "https://{web-app-fqdn}/"
    ]
  },
  "requiredResourceAccess": [
    {
      "resourceAppId": "{api-app-id}",
      "resourceAccess": [
        {
          "id": "{access_as_user-scope-id}",
          "type": "Scope"
        }
      ]
    }
  ]
}
```

### Container Apps Configuration

#### API Container App
- **CPU**: 0.5 cores
- **Memory**: 1 GB
- **Scaling**: 1-10 replicas based on HTTP requests
- **Port**: 4444
- **Environment**: Production-optimized Python with FastAPI

#### Web Container App  
- **CPU**: 0.25 cores
- **Memory**: 0.5 GB
- **Scaling**: 1-5 replicas based on HTTP requests
- **Port**: 80
- **Environment**: Nginx with SPA configuration

## Security Features

### 1. Zero Secrets in Code
- All secrets stored in Azure Key Vault
- Managed Identity access to Key Vault
- No hardcoded credentials in container images

### 2. Network Security
- Container Apps Environment with network isolation
- HTTPS-only communication
- CORS configured for web app domain only

### 3. Authentication & Authorization
- Azure AD integration with RBAC
- JWT token validation on all API calls
- Scope-based access control (admin vs user)

### 4. Monitoring & Logging
- Azure Log Analytics integration
- Application insights for performance monitoring
- Centralized log aggregation

## Customization

### 1. Environment-Specific Configuration

Create environment-specific parameter files:

```bash
# Development environment
cp infra/main.parameters.json infra/main.parameters.dev.json

# Production environment  
cp infra/main.parameters.json infra/main.parameters.prod.json
```

Edit parameters for each environment:
```json
{
  "parameters": {
    "environmentName": {"value": "mcpforge-dev"},
    "location": {"value": "East US"},
    "apiClientSecret": {"value": "${API_CLIENT_SECRET}"}
  }
}
```

### 2. Custom Domain Configuration

To use custom domains:

1. **Update Bicep templates** with custom domain resources
2. **Configure DNS** to point to Container Apps
3. **Update redirect URIs** in Azure AD app registrations

### 3. Additional Azure Services

The Bicep templates can be extended to include:
- **Azure SQL Database**: For production database
- **Azure Redis Cache**: For improved caching
- **Application Gateway**: For advanced routing and SSL termination
- **Azure Front Door**: For global load balancing

## Troubleshooting

### 1. Authentication Issues

**Problem**: Users cannot sign in
**Solution**: 
- Verify Azure AD app registrations
- Check redirect URIs match exactly
- Confirm tenant ID is correct

**Problem**: API returns 401 errors
**Solution**:
- Verify access token includes correct audience
- Check API app scopes are granted
- Confirm client secret is correctly stored in Key Vault

### 2. Deployment Issues

**Problem**: azd deployment fails
**Solution**:
- Check Azure subscription permissions
- Verify resource naming constraints
- Review deployment logs: `azd show`

**Problem**: Container apps fail to start
**Solution**:
- Check container logs: `az containerapp logs show`
- Verify environment variables are set
- Check container registry authentication

### 3. Networking Issues

**Problem**: Cannot access applications
**Solution**:
- Verify ingress configuration in Container Apps
- Check network security group rules
- Confirm HTTPS endpoints are accessible

## Monitoring and Maintenance

### 1. Health Monitoring

Both applications expose health check endpoints:
- **API**: `https://{api-fqdn}/health`
- **Web**: `https://{web-fqdn}/health`

### 2. Log Analysis

Use Azure Log Analytics to query application logs:

```kusto
ContainerAppConsoleLogs_CL
| where ContainerAppName_s == "ca-api-{resourceToken}"
| where TimeGenerated > ago(1h)
| order by TimeGenerated desc
```

### 3. Performance Monitoring

Monitor key metrics:
- **Response time**: API endpoint latency
- **Error rate**: 4xx/5xx HTTP responses
- **Throughput**: Requests per second
- **Resource utilization**: CPU and memory usage

### 4. Security Maintenance

Regular security tasks:
- **Rotate secrets**: Update API client secrets in Key Vault
- **Review access**: Audit Azure AD app permissions
- **Update dependencies**: Keep container images updated
- **Monitor alerts**: Configure alerts for security events

## Cost Optimization

### 1. Container Apps Scaling
- Configure minimum replicas to 0 for development
- Use consumption-based pricing for cost-effective scaling
- Set appropriate CPU/memory limits

### 2. Azure Services
- Use Basic tier for Azure Container Registry in development
- Configure Log Analytics retention policies
- Consider Azure Reservations for production workloads

## CI/CD Integration

The deployment includes GitHub Actions workflow for continuous deployment:

### 1. Required Secrets
```yaml
secrets:
  AZURE_CREDENTIALS: # Service principal credentials
  API_CLIENT_SECRET: # API app client secret

vars:
  AZURE_CLIENT_ID: # Service principal client ID
  AZURE_TENANT_ID: # Azure AD tenant ID
  AZURE_SUBSCRIPTION_ID: # Azure subscription ID
  AZURE_ENV_NAME: # Environment name
  AZURE_LOCATION: # Azure region
```

### 2. Workflow Triggers
- **Push to main**: Deploy to production
- **Pull request**: Deploy to staging environment
- **Manual dispatch**: On-demand deployment

This comprehensive setup provides a production-ready, secure, and scalable deployment of MCP Context Forge on Azure with zero manual configuration steps.