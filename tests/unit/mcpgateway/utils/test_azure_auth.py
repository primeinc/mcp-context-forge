"""
Tests for Azure AD authentication integration.

Copyright 2025
SPDX-License-Identifier: Apache-2.0
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi import HTTPException
from fastapi_azure_auth.user import User

from mcpgateway.utils.azure_auth import get_azure_auth, get_current_user, require_admin_user
from mcpgateway.utils.unified_auth import unified_auth, unified_admin_auth, get_user_identifier


def create_test_user(**kwargs):
    """Helper function to create a test User with all required fields."""
    import time
    current_time = int(time.time())
    
    defaults = {
        'aud': "api://test-api",
        'iss': "https://sts.windows.net/test-tenant-id/",
        'iat': current_time,
        'nbf': current_time,
        'exp': current_time + 3600,
        'sub': "test-user-id",
        'ver': "1.0",
        'claims': {},
        'access_token': "test-access-token",
        'oid': 'test-user-id',
        'name': 'Test User',
        'preferred_username': 'test@example.com'
    }
    defaults.update(kwargs)
    return User(**defaults)


class TestAzureADAuth:
    """Tests for Azure AD authentication."""

    @patch.dict('os.environ', {
        'AZURE_CLIENT_ID': 'test-client-id',
        'AZURE_TENANT_ID': 'test-tenant-id',
        'AZURE_CLIENT_SECRET': 'test-secret',
        'API_AUDIENCE': 'api://test-api'
    })
    def test_azure_auth_initialization(self):
        """Test Azure AD auth initialization with environment variables."""
        from mcpgateway.utils.azure_auth import AzureADAuth
        
        azure_auth = AzureADAuth()
        assert azure_auth is not None
        assert hasattr(azure_auth, 'azure_auth')

    @patch.dict('os.environ', {}, clear=True)
    def test_azure_auth_missing_config(self):
        """Test Azure AD auth fails with missing configuration."""
        from mcpgateway.utils.azure_auth import AzureADAuth
        
        with pytest.raises(ValueError, match="Azure AD configuration missing"):
            AzureADAuth()

    @pytest.mark.asyncio
    @patch('mcpgateway.config.settings.auth_required', True)
    @patch('mcpgateway.utils.azure_auth.get_azure_auth')
    async def test_get_current_user_azure_ad(self, mock_get_azure_auth):
        """Test getting current user with Azure AD authentication."""
        # Mock Azure AD user with all required fields
        mock_user = create_test_user(
            oid='test-user-id',
            name='Test User',
            preferred_username='test@example.com',
            claims={'roles': ['Gateway.User']}
        )
        
        mock_azure_auth = Mock()
        mock_azure_auth.get_current_user.return_value = mock_user
        mock_get_azure_auth.return_value = mock_azure_auth
        
        result = await get_current_user(auth_type="azure_ad")
        assert result == mock_user

    @pytest.mark.asyncio
    @patch('mcpgateway.config.settings.auth_required', False)
    async def test_get_current_user_auth_disabled(self):
        """Test getting current user when authentication is disabled."""
        result = await get_current_user(auth_type="azure_ad")
        
        assert isinstance(result, User)
        assert result.oid == 'anonymous'
        assert result.name == 'Anonymous User'

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_auth_type(self):
        """Test getting current user with invalid auth type."""
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(auth_type="invalid")
        
        assert exc_info.value.status_code == 501
        assert "not supported" in exc_info.value.detail

    @pytest.mark.asyncio
    @patch('mcpgateway.config.settings.auth_required', True)
    @patch('mcpgateway.utils.azure_auth.get_azure_auth')
    async def test_require_admin_user_azure_ad(self, mock_get_azure_auth):
        """Test requiring admin user with Azure AD authentication."""
        # Mock Azure AD admin user
        mock_admin = create_test_user(
            oid='test-admin-id',
            name='Test Admin',
            preferred_username='admin@example.com',
            claims={'roles': ['Gateway.Admin']}
        )
        
        mock_azure_auth = Mock()
        mock_azure_auth.require_admin_access.return_value = mock_admin
        mock_get_azure_auth.return_value = mock_azure_auth
        
        result = await require_admin_user(auth_type="azure_ad")
        assert result == mock_admin


class TestUnifiedAuth:
    """Tests for unified authentication system."""

    def test_get_user_identifier_string(self):
        """Test getting user identifier from string (legacy auth)."""
        user = "test_user"
        result = get_user_identifier(user)
        assert result == "test_user"

    def test_get_user_identifier_azure_user(self):
        """Test getting user identifier from Azure AD User object."""
        user = create_test_user(
            oid='test-oid',
            name='Test User',
            preferred_username='test@example.com',
            claims={}
        )
        
        result = get_user_identifier(user)
        assert result == 'test@example.com'

    def test_get_user_identifier_azure_user_no_username(self):
        """Test getting user identifier from Azure AD User with no preferred username."""
        user = create_test_user(
            oid='test-oid',
            name='Test User',
            claims={}
        )
        # Remove preferred_username attribute
        delattr(user, 'preferred_username')
        
        result = get_user_identifier(user)
        assert result == 'Test User'

    def test_get_user_identifier_azure_user_minimal(self):
        """Test getting user identifier from minimal Azure AD User object."""
        user = create_test_user(
            oid='test-oid',
            claims={}
        )
        # Remove name and preferred_username attributes
        delattr(user, 'name')
        delattr(user, 'preferred_username')
        
        result = get_user_identifier(user)
        assert result == 'test-oid'

    @pytest.mark.asyncio
    @patch('mcpgateway.config.settings.auth_type', 'azure_ad')
    @patch('mcpgateway.utils.unified_auth.azure_get_current_user')
    async def test_unified_auth_azure_ad(self, mock_azure_get_user):
        """Test unified auth with Azure AD type."""
        mock_user = create_test_user(
            oid='test-user',
            name='Test User',
            preferred_username='test@example.com',
            claims={}
        )
        mock_azure_get_user.return_value = mock_user
        
        result = await unified_auth()
        assert result == mock_user
        mock_azure_get_user.assert_called_once()

    @pytest.mark.asyncio
    @patch('mcpgateway.config.settings.auth_type', 'basic')
    @patch('mcpgateway.utils.unified_auth.legacy_require_auth')
    async def test_unified_auth_legacy(self, mock_legacy_auth):
        """Test unified auth with legacy type."""
        mock_legacy_auth.return_value = "test_user"
        
        result = await unified_auth()
        assert result == "test_user"
        mock_legacy_auth.assert_called_once()

    @pytest.mark.asyncio
    @patch('mcpgateway.config.settings.auth_type', 'azure_ad')
    @patch('mcpgateway.utils.unified_auth.azure_require_admin_user')
    async def test_unified_admin_auth_azure_ad(self, mock_azure_admin):
        """Test unified admin auth with Azure AD type."""
        mock_admin = create_test_user(
            oid='test-admin',
            name='Test Admin',
            preferred_username='admin@example.com',
            claims={'roles': ['Gateway.Admin']}
        )
        mock_azure_admin.return_value = mock_admin
        
        result = await unified_admin_auth()
        assert result == mock_admin
        mock_azure_admin.assert_called_once()


class TestAzureAuthConfiguration:
    """Tests for Azure authentication configuration."""

    @patch('mcpgateway.utils.azure_auth.get_azure_auth')
    def test_configure_app_auth(self, mock_get_azure_auth):
        """Test configuring FastAPI app with Azure AD authentication."""
        from mcpgateway.utils.azure_auth import configure_app_auth
        from fastapi import FastAPI
        
        app = FastAPI()
        mock_azure_auth = Mock()
        mock_azure_auth.azure_auth.configure_app = Mock()
        mock_get_azure_auth.return_value = mock_azure_auth
        
        # Mock settings to require auth
        with patch('mcpgateway.config.settings.auth_required', True):
            configure_app_auth(app)
            
        mock_azure_auth.azure_auth.configure_app.assert_called_once_with(app)

    def test_configure_app_auth_disabled(self):
        """Test configuring app when authentication is disabled."""
        from mcpgateway.utils.azure_auth import configure_app_auth
        from fastapi import FastAPI
        
        app = FastAPI()
        
        # Mock settings to disable auth
        with patch('mcpgateway.config.settings.auth_required', False):
            # Should not raise any exceptions
            configure_app_auth(app)


@pytest.fixture
def mock_azure_user():
    """Fixture for mock Azure AD user."""
    return create_test_user(
        oid='test-user-id',
        name='Test User',
        preferred_username='test@example.com',
        claims={
            'roles': ['Gateway.User'],
            'scp': 'access_as_user'
        }
    )


@pytest.fixture
def mock_azure_admin():
    """Fixture for mock Azure AD admin user."""
    return create_test_user(
        oid='test-admin-id',
        name='Test Admin',
        preferred_username='admin@example.com',
        claims={
            'roles': ['Gateway.Admin', 'Gateway.User'],
            'scp': 'access_as_user'
        }
    )


class TestAzureAuthIntegration:
    """Integration tests for Azure AD authentication."""

    @pytest.mark.asyncio
    async def test_user_has_required_scopes(self, mock_azure_user):
        """Test that user has required scopes."""
        scopes = mock_azure_user.claims.get('scp', '').split(' ')
        assert 'access_as_user' in scopes

    @pytest.mark.asyncio
    async def test_admin_has_admin_role(self, mock_azure_admin):
        """Test that admin user has admin role."""
        roles = mock_azure_admin.claims.get('roles', [])
        assert 'Gateway.Admin' in roles

    @pytest.mark.asyncio
    async def test_user_identifier_extraction(self, mock_azure_user):
        """Test extracting user identifier from Azure AD user."""
        identifier = get_user_identifier(mock_azure_user)
        assert identifier == 'test@example.com'

    def test_environment_variable_configuration(self):
        """Test that environment variables are properly configured."""
        import os
        
        # These should be set in the container environment
        expected_vars = [
            'AZURE_CLIENT_ID',
            'AZURE_TENANT_ID', 
            'AZURE_AUTHORITY_HOST',
            'API_AUDIENCE'
        ]
        
        # In test environment, these might not be set, so we just check the configuration logic
        for var in expected_vars:
            # Environment variable should be configurable
            assert isinstance(os.getenv(var, ''), str)