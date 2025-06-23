# -*- coding: utf-8 -*-
"""
Azure AD Authentication Module for MCP Gateway.

Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Mihai Criveti

This module provides Azure AD authentication using fastapi-azure-auth.
It replaces the legacy JWT and basic auth systems with Azure AD/MSAL authentication.
"""

import os
from typing import Optional

from fastapi import HTTPException, status
from fastapi_azure_auth import SingleTenantAzureAuthorizationCodeBearer, MultiTenantAzureAuthorizationCodeBearer
from fastapi_azure_auth.user import User

from mcpgateway.config import settings

class AzureADAuth:
    """Azure AD Authentication handler."""
    
    def __init__(self):
        """Initialize Azure AD authentication."""
        # Load Azure AD configuration from environment
        self.azure_client_id = os.getenv('AZURE_CLIENT_ID', '')
        self.azure_tenant_id = os.getenv('AZURE_TENANT_ID', '')
        self.azure_client_secret = os.getenv('AZURE_CLIENT_SECRET', '')
        self.api_audience = os.getenv('API_AUDIENCE', f'api://{self.azure_client_id}')
        
        if not self.azure_client_id or not self.azure_tenant_id:
            raise ValueError("Azure AD configuration missing. Set AZURE_CLIENT_ID and AZURE_TENANT_ID environment variables.")
        
        # Initialize Azure Auth based on tenant configuration
        if self.azure_tenant_id and self.azure_tenant_id != 'common':
            # Single tenant configuration
            self.azure_auth = SingleTenantAzureAuthorizationCodeBearer(
                app_client_id=self.azure_client_id,
                tenant_id=self.azure_tenant_id,
                scopes={
                    f'{self.api_audience}/access_as_user': 'Access MCP Gateway API',
                    f'{self.api_audience}/Gateway.Admin': 'Administrative access to MCP Gateway',
                    f'{self.api_audience}/Gateway.User': 'User access to MCP Gateway'
                }
            )
        else:
            # Multi-tenant configuration
            self.azure_auth = MultiTenantAzureAuthorizationCodeBearer(
                app_client_id=self.azure_client_id,
                scopes={
                    f'{self.api_audience}/access_as_user': 'Access MCP Gateway API',
                    f'{self.api_audience}/Gateway.Admin': 'Administrative access to MCP Gateway',
                    f'{self.api_audience}/Gateway.User': 'User access to MCP Gateway'
                }
            )

    def get_current_user(self) -> User:
        """Get the current authenticated user."""
        # This will be used as a FastAPI Depends() function
        return self.azure_auth

    def get_current_user_optional(self) -> Optional[User]:
        """Get the current user if authenticated, None otherwise."""
        # For now, return the azure_auth instance
        return self.azure_auth

    def require_admin_access(self) -> User:
        """Require admin access to the API."""
        # This will be used as a FastAPI Depends() function
        return self.azure_auth

    def require_user_access(self) -> User:
        """Require user access to the API."""
        # This will be used as a FastAPI Depends() function  
        return self.azure_auth

# Global instance
azure_ad_auth = None

def get_azure_auth() -> AzureADAuth:
    """Get or create the Azure AD auth instance."""
    global azure_ad_auth
    if azure_ad_auth is None:
        azure_ad_auth = AzureADAuth()
    return azure_ad_auth

async def get_current_user(auth_type: str = "azure_ad") -> User:
    """
    Get the current authenticated user.
    
    Args:
        auth_type: The authentication type (should be 'azure_ad')
        
    Returns:
        The authenticated user
        
    Raises:
        HTTPException: If authentication fails or auth type is not supported
    """
    if not settings.auth_required:
        # Return anonymous user if auth is disabled
        import time
        current_time = int(time.time())
        return User(
            aud="api://anonymous",
            iss="https://anonymous/",
            iat=current_time,
            nbf=current_time,
            exp=current_time + 3600,
            sub="anonymous",
            ver="1.0",
            claims={},
            access_token="anonymous-token",
            oid='anonymous',
            name='Anonymous User',
            preferred_username='anonymous'
        )
    
    if auth_type != "azure_ad":
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Authentication type '{auth_type}' not supported. Use 'azure_ad'."
        )
    
    try:
        azure_auth = get_azure_auth()
        user_dependency = azure_auth.get_current_user()
        # Note: This needs to be called within a FastAPI dependency context
        return user_dependency
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Azure AD authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

async def require_admin_user(auth_type: str = "azure_ad") -> User:
    """
    Require administrative access.
    
    Args:
        auth_type: The authentication type (should be 'azure_ad')
        
    Returns:
        The authenticated admin user
        
    Raises:
        HTTPException: If authentication fails or user lacks admin access
    """
    if not settings.auth_required:
        # Return anonymous admin if auth is disabled
        import time
        current_time = int(time.time())
        return User(
            aud="api://anonymous-admin",
            iss="https://anonymous/",
            iat=current_time,
            nbf=current_time,
            exp=current_time + 3600,
            sub="anonymous-admin",
            ver="1.0",
            claims={'roles': ['Gateway.Admin']},
            access_token="anonymous-admin-token",
            oid='anonymous-admin',
            name='Anonymous Admin',
            preferred_username='anonymous-admin'
        )
    
    if auth_type != "azure_ad":
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Authentication type '{auth_type}' not supported. Use 'azure_ad'."
        )
    
    try:
        azure_auth = get_azure_auth()
        admin_dependency = azure_auth.require_admin_access()
        # Note: This needs to be called within a FastAPI dependency context
        return admin_dependency
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative access required",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

def configure_app_auth(app):
    """Configure FastAPI app with Azure AD authentication."""
    if settings.auth_required:
        azure_auth = get_azure_auth()
        azure_auth.azure_auth.configure_app(app)