# -*- coding: utf-8 -*-
"""
Unified Authentication Dependencies for MCP Gateway.

Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Mihai Criveti

This module provides unified authentication dependencies that can work with
both legacy auth (JWT/basic) and Azure AD authentication.
"""

from typing import Union
from fastapi import Depends
from fastapi_azure_auth.user import User

from mcpgateway.config import settings
from mcpgateway.utils.azure_auth import get_current_user as azure_get_current_user, require_admin_user as azure_require_admin_user
from mcpgateway.utils.verify_credentials import require_auth as legacy_require_auth


async def unified_auth() -> Union[str, User]:
    """
    Unified authentication dependency that supports both legacy and Azure AD auth.
    
    Returns:
        Either a string (legacy auth) or User object (Azure AD auth)
    """
    auth_type = getattr(settings, 'auth_type', 'basic')
    
    if auth_type == 'azure_ad':
        # Use Azure AD authentication
        return await azure_get_current_user()
    else:
        # Use legacy authentication (basic/JWT)
        return await legacy_require_auth()


async def unified_admin_auth() -> Union[str, User]:
    """
    Unified admin authentication dependency that supports both legacy and Azure AD auth.
    
    Returns:
        Either a string (legacy auth) or User object (Azure AD auth)
    """
    auth_type = getattr(settings, 'auth_type', 'basic')
    
    if auth_type == 'azure_ad':
        # Use Azure AD admin authentication
        return await azure_require_admin_user()
    else:
        # Use legacy authentication (basic/JWT) - admin is same as regular auth in legacy
        return await legacy_require_auth()


def get_user_identifier(user: Union[str, User]) -> str:
    """
    Extract user identifier from either legacy auth (string) or Azure AD (User object).
    
    Args:
        user: Either a string username or Azure AD User object
        
    Returns:
        String identifier for the user
    """
    if isinstance(user, str):
        return user
    elif hasattr(user, 'preferred_username'):
        return user.preferred_username
    elif hasattr(user, 'name'):
        return user.name
    elif hasattr(user, 'oid'):
        return user.oid
    else:
        return str(user)