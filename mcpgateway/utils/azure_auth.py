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
from fastapi_azure_auth import SingleTenantAzureAuth, MultiTenantAzureAuth
from fastapi_azure_auth.user import User

from mcpgateway.config import settings

# Azure AD Configuration
AZURE_CLIENT_ID = os.getenv('AZURE_CLIENT_ID', '')
AZURE_TENANT_ID = os.getenv('AZURE_TENANT_ID', '')
AZURE_CLIENT_SECRET = os.getenv('AZURE_CLIENT_SECRET', '')
API_AUDIENCE = os.getenv('API_AUDIENCE', f'api://{AZURE_CLIENT_ID}')

class AzureADAuth:
    """Azure AD Authentication handler."""
    
    def __init__(self):
        """Initialize Azure AD authentication."""
        if not AZURE_CLIENT_ID or not AZURE_TENANT_ID:
            raise ValueError("Azure AD configuration missing. Set AZURE_CLIENT_ID and AZURE_TENANT_ID environment variables.")
        
        # Initialize Azure Auth based on tenant configuration
        if AZURE_TENANT_ID and AZURE_TENANT_ID != 'common':
            # Single tenant configuration
            self.azure_auth = SingleTenantAzureAuth(
                app_client_id=AZURE_CLIENT_ID,
                tenant_id=AZURE_TENANT_ID,
                scopes={
                    f'{API_AUDIENCE}/access_as_user': 'Access MCP Gateway API',
                    f'{API_AUDIENCE}/Gateway.Admin': 'Administrative access to MCP Gateway',
                    f'{API_AUDIENCE}/Gateway.User': 'User access to MCP Gateway'
                }
            )
        else:
            # Multi-tenant configuration
            self.azure_auth = MultiTenantAzureAuth(
                app_client_id=AZURE_CLIENT_ID,
                scopes={
                    f'{API_AUDIENCE}/access_as_user': 'Access MCP Gateway API',
                    f'{API_AUDIENCE}/Gateway.Admin': 'Administrative access to MCP Gateway',
                    f'{API_AUDIENCE}/Gateway.User': 'User access to MCP Gateway'
                }
            )

    def get_current_user(self) -> User:
        """Get the current authenticated user."""
        return self.azure_auth.auth_required

    def get_current_user_optional(self) -> Optional[User]:
        """Get the current user if authenticated, None otherwise."""
        return self.azure_auth.auth_optional

    def require_admin_access(self) -> User:
        """Require admin access to the API."""
        return self.azure_auth.auth_required_with_scopes([f'{API_AUDIENCE}/Gateway.Admin'])

    def require_user_access(self) -> User:
        """Require user access to the API."""
        return self.azure_auth.auth_required_with_scopes([
            f'{API_AUDIENCE}/Gateway.User',
            f'{API_AUDIENCE}/Gateway.Admin'
        ])

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
        return User(
            oid='anonymous',
            name='Anonymous User',
            preferred_username='anonymous',
            claims={}
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
        return User(
            oid='anonymous-admin',
            name='Anonymous Admin',
            preferred_username='anonymous-admin',
            claims={'roles': ['Gateway.Admin']}
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