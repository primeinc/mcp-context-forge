# Quick Start: Azure Deployment

Deploy MCP Context Forge to Azure with Azure AD authentication in one command.

## Prerequisites

1. [Azure Developer CLI (azd)](https://docs.microsoft.com/en-us/azure/developer/azure-developer-cli/install-azd)
2. [Azure CLI](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli)
3. Azure subscription with Contributor access

## One-Command Deployment

```bash
# Clone the repository
git clone https://github.com/primeinc/mcp-context-forge.git
cd mcp-context-forge

# Deploy to Azure (this will take 10-15 minutes)
azd up
```

Follow the prompts:
- **Environment name**: e.g., `mcpforge-prod`
- **Azure subscription**: Select your subscription
- **Azure region**: e.g., `East US 2`

## What Gets Deployed

### Azure Resources
- **Container Apps Environment**: Serverless container hosting
- **Azure Container Registry**: Private container images
- **Azure Key Vault**: Secure secrets storage
- **Azure Log Analytics**: Centralized logging

### Applications
- **API Container App**: MCP Gateway with Azure AD auth
- **Web Container App**: Admin UI with MSAL auth

### Azure AD
- **API App Registration**: Backend with scopes/roles
- **Web App Registration**: SPA with permissions

## Post-Deployment

### 1. Access Applications

After deployment, azd will show the URLs:

```
API Endpoint: https://ca-api-xyz123.azurecontainerapps.io
Web UI: https://ca-web-xyz123.azurecontainerapps.io
```

### 2. Assign User Roles

Users need Azure AD roles to access the application:

```bash
# Get the API app ID
API_APP_ID=$(azd env get-value AZURE_API_CLIENT_ID)

# Assign Gateway.Admin role to a user
az ad app permission admin-consent --id $API_APP_ID

# Add user to app role (replace with actual user email)
az ad app owner add --id $API_APP_ID --owner-object-id $(az ad user show --id user@domain.com --query id -o tsv)
```

### 3. Validate Deployment

```bash
# Run validation script
python scripts/validate-azure-deployment.py
```

### 4. View Logs

```bash
# View API logs
az containerapp logs show \
  --name $(azd env get-value API_NAME) \
  --resource-group $(azd env get-value AZURE_RESOURCE_GROUP) \
  --follow

# View Web logs
az containerapp logs show \
  --name $(azd env get-value WEB_NAME) \
  --resource-group $(azd env get-value AZURE_RESOURCE_GROUP) \
  --follow
```

## Environment Management

### Multiple Environments

```bash
# Create development environment
azd env new mcpforge-dev
azd env select mcpforge-dev
azd up

# Switch back to production
azd env select mcpforge-prod
```

### Update Deployment

```bash
# Update infrastructure
azd provision

# Update applications only
azd deploy
```

### Clean Up

```bash
# Delete entire environment
azd down --purge
```

## Customization

### Environment Variables

Edit `.azure/{environment-name}/.env`:

```bash
# Custom configuration
LOG_LEVEL=DEBUG
CORS_ENABLED=true
```

### Custom Domain

1. Add custom domain to Container Apps
2. Update Azure AD redirect URIs
3. Configure DNS records

## Troubleshooting

### Common Issues

**Problem**: `azd up` fails with permission errors
```bash
# Solution: Ensure you have Contributor role
az role assignment create \
  --assignee $(az account show --query user.name -o tsv) \
  --role Contributor \
  --scope /subscriptions/$(az account show --query id -o tsv)
```

**Problem**: Web app shows authentication errors
```bash
# Solution: Check Azure AD app registrations
az ad app list --display-name "mcp-context-forge-web-*"
```

**Problem**: API returns 500 errors
```bash
# Solution: Check container logs
az containerapp logs show --name ca-api-* --resource-group rg-*
```

### Support

For detailed troubleshooting, see [AZURE_DEPLOYMENT.md](./AZURE_DEPLOYMENT.md)

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Azure AD      │    │  Container Apps  │    │   Key Vault     │
│                 │    │                  │    │                 │
│ ┌─────────────┐ │    │ ┌──────────────┐ │    │ ┌─────────────┐ │
│ │ API App Reg │ │◄───┤ │     API      │ │◄───┤ │   Secrets   │ │
│ └─────────────┘ │    │ │  Container   │ │    │ └─────────────┘ │
│ ┌─────────────┐ │    │ └──────────────┘ │    └─────────────────┘
│ │ Web App Reg │ │    │ ┌──────────────┐ │
│ └─────────────┘ │◄───┤ │     Web      │ │
└─────────────────┘    │ │  Container   │ │
                       │ └──────────────┘ │
                       └──────────────────┘
```

This deployment provides production-ready Azure-native hosting with zero manual configuration steps.