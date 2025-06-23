#!/usr/bin/env python3
"""
Azure Deployment Validation Script for MCP Context Forge.

This script validates that the Azure deployment is working correctly by testing:
1. Infrastructure deployment status
2. Container app health endpoints
3. Azure AD authentication configuration
4. API endpoint accessibility
"""

import asyncio
import json
import sys
from typing import Dict, Any, Optional
import subprocess
import httpx
from dataclasses import dataclass


@dataclass
class ValidationConfig:
    """Configuration for deployment validation."""
    environment_name: str
    subscription_id: str
    resource_group: str
    api_base_url: str
    web_base_url: str
    tenant_id: str
    api_client_id: str
    web_client_id: str


class AzureDeploymentValidator:
    """Validates Azure deployment of MCP Context Forge."""

    def __init__(self, config: ValidationConfig):
        self.config = config
        self.client = httpx.AsyncClient(timeout=30.0)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    def run_azure_cli(self, command: list) -> Dict[str, Any]:
        """Run Azure CLI command and return JSON result."""
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True
            )
            return json.loads(result.stdout) if result.stdout.strip() else {}
        except subprocess.CalledProcessError as e:
            print(f"❌ Azure CLI command failed: {' '.join(command)}")
            print(f"Error: {e.stderr}")
            return {}
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse Azure CLI output: {e}")
            return {}

    def validate_infrastructure(self) -> bool:
        """Validate that all Azure resources are deployed correctly."""
        print("🔍 Validating Azure infrastructure...")

        # Check resource group
        rg_command = [
            "az", "group", "show",
            "--name", self.config.resource_group,
            "--subscription", self.config.subscription_id
        ]
        rg_result = self.run_azure_cli(rg_command)
        if not rg_result:
            print(f"❌ Resource group {self.config.resource_group} not found")
            return False
        print(f"✅ Resource group {self.config.resource_group} exists")

        # Check container apps
        apps_command = [
            "az", "containerapp", "list",
            "--resource-group", self.config.resource_group,
            "--subscription", self.config.subscription_id
        ]
        apps_result = self.run_azure_cli(apps_command)
        if not apps_result or len(apps_result) < 2:
            print("❌ Container apps not found or incomplete")
            return False

        api_app = next((app for app in apps_result if "api" in app["name"]), None)
        web_app = next((app for app in apps_result if "web" in app["name"]), None)

        if not api_app:
            print("❌ API container app not found")
            return False
        if not web_app:
            print("❌ Web container app not found")
            return False

        print(f"✅ API container app: {api_app['name']}")
        print(f"✅ Web container app: {web_app['name']}")

        # Check Key Vault
        kv_command = [
            "az", "keyvault", "list",
            "--resource-group", self.config.resource_group,
            "--subscription", self.config.subscription_id
        ]
        kv_result = self.run_azure_cli(kv_command)
        if not kv_result:
            print("❌ Key Vault not found")
            return False
        print(f"✅ Key Vault: {kv_result[0]['name']}")

        return True

    async def validate_health_endpoints(self) -> bool:
        """Validate that health endpoints are accessible."""
        print("🏥 Validating health endpoints...")

        # Test API health endpoint
        try:
            api_health_url = f"{self.config.api_base_url}/health"
            api_response = await self.client.get(api_health_url)
            if api_response.status_code == 200:
                print(f"✅ API health endpoint accessible: {api_health_url}")
            else:
                print(f"❌ API health endpoint failed: {api_response.status_code}")
                return False
        except Exception as e:
            print(f"❌ API health endpoint error: {e}")
            return False

        # Test Web health endpoint
        try:
            web_health_url = f"{self.config.web_base_url}/health"
            web_response = await self.client.get(web_health_url)
            if web_response.status_code == 200:
                print(f"✅ Web health endpoint accessible: {web_health_url}")
            else:
                print(f"❌ Web health endpoint failed: {web_response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Web health endpoint error: {e}")
            return False

        return True

    def validate_azure_ad_apps(self) -> bool:
        """Validate Azure AD app registrations."""
        print("🔐 Validating Azure AD app registrations...")

        # Check API app registration
        api_app_command = [
            "az", "ad", "app", "show",
            "--id", self.config.api_client_id
        ]
        api_app_result = self.run_azure_cli(api_app_command)
        if not api_app_result:
            print(f"❌ API app registration not found: {self.config.api_client_id}")
            return False
        print(f"✅ API app registration: {api_app_result['displayName']}")

        # Check Web app registration
        web_app_command = [
            "az", "ad", "app", "show",
            "--id", self.config.web_client_id
        ]
        web_app_result = self.run_azure_cli(web_app_command)
        if not web_app_result:
            print(f"❌ Web app registration not found: {self.config.web_client_id}")
            return False
        print(f"✅ Web app registration: {web_app_result['displayName']}")

        return True

    async def validate_api_endpoints(self) -> bool:
        """Validate API endpoints (without authentication)."""
        print("🔌 Validating API endpoints...")

        # Test endpoints that should work without auth (if auth is disabled)
        endpoints_to_test = [
            "/docs",
            "/openapi.json",
        ]

        for endpoint in endpoints_to_test:
            try:
                url = f"{self.config.api_base_url}{endpoint}"
                response = await self.client.get(url)
                if response.status_code in [200, 401, 403]:  # 401/403 is expected for protected endpoints
                    print(f"✅ Endpoint accessible: {endpoint}")
                else:
                    print(f"❌ Endpoint failed: {endpoint} (status: {response.status_code})")
                    return False
            except Exception as e:
                print(f"❌ Endpoint error {endpoint}: {e}")
                return False

        return True

    async def validate_web_app(self) -> bool:
        """Validate web application."""
        print("🌐 Validating web application...")

        try:
            response = await self.client.get(self.config.web_base_url)
            if response.status_code == 200:
                content = response.text
                # Check for expected content
                if "MCP Context Forge" in content and "Azure AD" in content:
                    print("✅ Web application loaded with expected content")
                    return True
                else:
                    print("❌ Web application content validation failed")
                    return False
            else:
                print(f"❌ Web application failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Web application error: {e}")
            return False

    async def run_validation(self) -> bool:
        """Run complete validation."""
        print("🚀 Starting Azure deployment validation...\n")

        results = []

        # Infrastructure validation
        results.append(self.validate_infrastructure())

        # Health endpoints validation
        results.append(await self.validate_health_endpoints())

        # Azure AD validation
        results.append(self.validate_azure_ad_apps())

        # API endpoints validation
        results.append(await self.validate_api_endpoints())

        # Web app validation
        results.append(await self.validate_web_app())

        # Summary
        passed = sum(results)
        total = len(results)

        print(f"\n📊 Validation Summary: {passed}/{total} checks passed")

        if passed == total:
            print("🎉 All validations passed! Deployment is successful.")
            return True
        else:
            print("❌ Some validations failed. Please check the deployment.")
            return False


def load_config_from_azd() -> Optional[ValidationConfig]:
    """Load configuration from azd environment."""
    try:
        # Get azd environment
        result = subprocess.run(
            ["azd", "env", "get-values"],
            capture_output=True,
            text=True,
            check=True
        )

        env_vars = {}
        for line in result.stdout.strip().split('\n'):
            if '=' in line:
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip().strip('"')

        return ValidationConfig(
            environment_name=env_vars.get('AZURE_ENV_NAME', ''),
            subscription_id=env_vars.get('AZURE_SUBSCRIPTION_ID', ''),
            resource_group=env_vars.get('AZURE_RESOURCE_GROUP', ''),
            api_base_url=env_vars.get('API_BASE_URL', ''),
            web_base_url=env_vars.get('WEB_BASE_URL', ''),
            tenant_id=env_vars.get('AZURE_TENANT_ID', ''),
            api_client_id=env_vars.get('AZURE_API_CLIENT_ID', ''),
            web_client_id=env_vars.get('AZURE_WEB_CLIENT_ID', ''),
        )
    except subprocess.CalledProcessError:
        print("❌ Failed to get azd environment. Make sure you've run 'azd up' successfully.")
        return None
    except Exception as e:
        print(f"❌ Error loading configuration: {e}")
        return None


async def main():
    """Main validation function."""
    config = load_config_from_azd()
    if not config:
        sys.exit(1)

    async with AzureDeploymentValidator(config) as validator:
        success = await validator.run_validation()
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())