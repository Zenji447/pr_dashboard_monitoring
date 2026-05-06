"""
Property-Based Tests for Tenant Integrations

This module implements property-based tests for tenant integration management
(Slack, Google Sheets, Email, Webhook).

Correctness Properties Validated:
- Property 18: Enabled integration returns config
- Property 19: Disabled integration returns None
- Property 20: Integration type validation
- Property 21: Integration config is valid JSON
- Property 22: Multiple integrations per tenant supported
"""
import secrets
import sqlite3
import json
from typing import Dict, Any
import pytest
from hypothesis import given, strategies as st, settings, assume, HealthCheck

from integrations.tenant_context import (
    get_tenant_by_api_key,
    get_tenant_by_id,
    clear_tenant_cache
)


# ============================================================================
# Hypothesis Strategies
# ============================================================================

@st.composite
def integration_type_strategy(draw):
    """Strategy for generating valid integration types."""
    return draw(st.sampled_from(['slack', 'sheets', 'email', 'webhook']))


@st.composite
def slack_config_strategy(draw):
    """Strategy for generating valid Slack configuration."""
    return {
        'token': draw(st.text(min_size=10, max_size=100, alphabet='abcdefghijklmnopqrstuvwxyz0123456789-')),
        'channel': draw(st.text(min_size=2, max_size=50).map(lambda x: f'#{x}'))
    }


@st.composite
def sheets_config_strategy(draw):
    """Strategy for generating valid Google Sheets configuration."""
    return {
        'sheet_id': draw(st.text(min_size=20, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')),
        'credentials_path': draw(st.text(min_size=5, max_size=100).map(lambda x: f'/path/to/{x}.json'))
    }


@st.composite
def email_config_strategy(draw):
    """Strategy for generating valid Email configuration."""
    return {
        'smtp_host': draw(st.text(min_size=5, max_size=50).map(lambda x: f'{x}.com')),
        'smtp_port': draw(st.integers(min_value=25, max_value=587)),
        'from_email': draw(st.text(min_size=3, max_size=30).map(lambda x: f'{x}@example.com')),
        'to_emails': draw(st.lists(st.text(min_size=3, max_size=20).map(lambda x: f'{x}@example.com'), min_size=1, max_size=5))
    }


@st.composite
def webhook_config_strategy(draw):
    """Strategy for generating valid Webhook configuration."""
    return {
        'url': draw(st.text(min_size=10, max_size=100).map(lambda x: f'https://webhook.site/{x}')),
        'method': draw(st.sampled_from(['POST', 'PUT'])),
        'headers': draw(st.dictionaries(
            st.text(min_size=1, max_size=20),
            st.text(min_size=1, max_size=50),
            min_size=0,
            max_size=5
        ))
    }


@st.composite
def integration_config_strategy(draw, integration_type):
    """Strategy for generating config based on integration type."""
    if integration_type == 'slack':
        return draw(slack_config_strategy())
    elif integration_type == 'sheets':
        return draw(sheets_config_strategy())
    elif integration_type == 'email':
        return draw(email_config_strategy())
    elif integration_type == 'webhook':
        return draw(webhook_config_strategy())
    else:
        return {}


# ============================================================================
# Property 18: Enabled Integration Returns Config
# ============================================================================

@pytest.mark.property
class TestEnabledIntegrationReturnsConfig:
    """
    Property 18: For any tenant T with enabled integration I of type T,
    T.get_integration(T) returns the integration config.
    """
    
    @given(integration_type=integration_type_strategy())
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=40)
    def test_enabled_integration_returns_config(self, integration_type, create_tenant, cleanup_tenants):
        """Verify that enabled integrations return their config."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        
        # Create appropriate config based on type
        if integration_type == 'slack':
            config = {'token': 'xoxb-test-token', 'channel': '#test'}
        elif integration_type == 'sheets':
            config = {'sheet_id': '1234567890', 'credentials_path': '/path/to/creds.json'}
        elif integration_type == 'email':
            config = {'smtp_host': 'smtp.example.com', 'smtp_port': 587, 'from_email': 'test@example.com'}
        else:  # webhook
            config = {'url': 'https://webhook.site/test', 'method': 'POST'}
        
        # Create tenant with enabled integration
        integrations = {
            integration_type: {
                'enabled': True,
                'config': config
            }
        }
        
        create_tenant(api_key=api_key, integrations=integrations)
        
        # Retrieve tenant and check integration
        tenant = get_tenant_by_api_key(api_key)
        assert tenant is not None
        
        integration = tenant.get_integration(integration_type)
        assert integration is not None, f"Enabled {integration_type} integration should return config"
        assert integration['enabled'] is True
        assert integration['config'] == config
    
    def test_has_integration_returns_true_for_enabled(self, create_tenant, sample_integration_config):
        """Verify that has_integration returns True for enabled integrations."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        create_tenant(api_key=api_key, integrations=sample_integration_config)
        
        tenant = get_tenant_by_api_key(api_key)
        
        assert tenant.has_integration('slack') is True
        assert tenant.has_integration('sheets') is True


# ============================================================================
# Property 19: Disabled Integration Returns None
# ============================================================================

@pytest.mark.property
class TestDisabledIntegrationReturnsNone:
    """
    Property 19: For any tenant T with disabled integration I of type T,
    T.get_integration(T) returns None or T.has_integration(T) returns False.
    """
    
    @given(integration_type=integration_type_strategy())
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=40)
    def test_disabled_integration_returns_none_or_false(self, integration_type, create_tenant, cleanup_tenants):
        """Verify that disabled integrations return None or False."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        
        # Create tenant with disabled integration
        integrations = {
            integration_type: {
                'enabled': False,
                'config': {'test': 'config'}
            }
        }
        
        create_tenant(api_key=api_key, integrations=integrations)
        
        # Retrieve tenant and check integration
        tenant = get_tenant_by_api_key(api_key)
        assert tenant is not None
        
        # has_integration should return False
        assert tenant.has_integration(integration_type) is False, \
            f"Disabled {integration_type} integration should return False from has_integration"
    
    def test_nonexistent_integration_returns_none(self, create_tenant):
        """Verify that non-existent integrations return None."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        create_tenant(api_key=api_key)  # No integrations
        
        tenant = get_tenant_by_api_key(api_key)
        
        # All integration types should return None
        assert tenant.get_integration('slack') is None
        assert tenant.get_integration('sheets') is None
        assert tenant.get_integration('email') is None
        assert tenant.get_integration('webhook') is None
        
        # has_integration should return False
        assert tenant.has_integration('slack') is False
        assert tenant.has_integration('sheets') is False


# ============================================================================
# Property 20: Integration Type Validation
# ============================================================================

@pytest.mark.property
class TestIntegrationTypeValidation:
    """
    Property 20: For any integration I, I.integration_type must be one of:
    slack, sheets, email, webhook.
    """
    
    @given(integration_type=integration_type_strategy())
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=40)
    def test_valid_integration_types_accepted(self, integration_type, create_tenant, cleanup_tenants):
        """Verify that valid integration types are accepted."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        
        integrations = {
            integration_type: {
                'enabled': True,
                'config': {'test': 'config'}
            }
        }
        
        tenant_id = create_tenant(api_key=api_key, integrations=integrations)
        
        # Verify integration was stored
        tenant = get_tenant_by_api_key(api_key)
        integration = tenant.get_integration(integration_type)
        
        assert integration is not None
        assert integration_type in ['slack', 'sheets', 'email', 'webhook']
    
    def test_invalid_integration_type_rejected(self, db_connection, create_tenant):
        """Verify that invalid integration types are rejected by database."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        tenant_id = create_tenant(api_key=api_key)
        
        with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
            cursor = db_connection.cursor()
            cursor.execute("""
                INSERT INTO tenant_integrations (tenant_id, integration_type, enabled, config)
                VALUES (?, ?, ?, ?)
            """, (tenant_id, 'invalid_type', 1, '{}'))
            db_connection.commit()


# ============================================================================
# Property 21: Integration Config is Valid JSON
# ============================================================================

@pytest.mark.property
class TestIntegrationConfigValidJSON:
    """
    Property 21: For any integration I, I.config must be valid JSON.
    """
    
    @given(integration_type=integration_type_strategy())
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=40)
    def test_integration_config_is_valid_json(self, integration_type, create_tenant, db_connection, cleanup_tenants):
        """Verify that integration configs are stored as valid JSON."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        
        # Create complex config
        config = {
            'string_field': 'test',
            'number_field': 123,
            'boolean_field': True,
            'array_field': [1, 2, 3],
            'object_field': {'nested': 'value'}
        }
        
        integrations = {
            integration_type: {
                'enabled': True,
                'config': config
            }
        }
        
        tenant_id = create_tenant(api_key=api_key, integrations=integrations)
        
        # Retrieve from database and verify it's valid JSON
        cursor = db_connection.cursor()
        cursor.execute("""
            SELECT config FROM tenant_integrations 
            WHERE tenant_id = ? AND integration_type = ?
        """, (tenant_id, integration_type))
        
        row = cursor.fetchone()
        assert row is not None
        
        # Should be able to parse as JSON
        stored_config = json.loads(row[0])
        assert stored_config == config
    
    def test_empty_config_is_valid_json(self, create_tenant, db_connection):
        """Verify that empty config is stored as valid JSON."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        
        integrations = {
            'slack': {
                'enabled': True,
                'config': {}
            }
        }
        
        tenant_id = create_tenant(api_key=api_key, integrations=integrations)
        
        # Verify empty config is stored as '{}'
        cursor = db_connection.cursor()
        cursor.execute("""
            SELECT config FROM tenant_integrations 
            WHERE tenant_id = ? AND integration_type = ?
        """, (tenant_id, 'slack'))
        
        row = cursor.fetchone()
        config = json.loads(row[0])
        assert config == {}


# ============================================================================
# Property 22: Multiple Integrations Per Tenant
# ============================================================================

@pytest.mark.property
class TestMultipleIntegrationsPerTenant:
    """
    Property 22: For any tenant T, T can have multiple integrations of
    different types simultaneously.
    """
    
    def test_tenant_can_have_multiple_integrations(self, create_tenant, sample_integration_config):
        """Verify that a tenant can have multiple integrations."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        
        # Create tenant with multiple integrations
        create_tenant(api_key=api_key, integrations=sample_integration_config)
        
        tenant = get_tenant_by_api_key(api_key)
        
        # Verify all integrations exist
        slack_integration = tenant.get_integration('slack')
        sheets_integration = tenant.get_integration('sheets')
        
        assert slack_integration is not None
        assert sheets_integration is not None
        
        assert slack_integration['enabled'] is True
        assert sheets_integration['enabled'] is True
    
    def test_tenant_can_have_all_integration_types(self, create_tenant):
        """Verify that a tenant can have all 4 integration types."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        
        # Create tenant with all integration types
        integrations = {
            'slack': {'enabled': True, 'config': {'token': 'slack_token'}},
            'sheets': {'enabled': True, 'config': {'sheet_id': 'sheet_123'}},
            'email': {'enabled': True, 'config': {'smtp_host': 'smtp.example.com'}},
            'webhook': {'enabled': True, 'config': {'url': 'https://webhook.site/test'}}
        }
        
        create_tenant(api_key=api_key, integrations=integrations)
        
        tenant = get_tenant_by_api_key(api_key)
        
        # Verify all 4 integrations exist
        assert tenant.has_integration('slack') is True
        assert tenant.has_integration('sheets') is True
        assert tenant.has_integration('email') is True
        assert tenant.has_integration('webhook') is True
    
    def test_duplicate_integration_type_rejected(self, create_tenant, db_connection):
        """Verify that duplicate integration types for same tenant are rejected."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        tenant_id = create_tenant(api_key=api_key)
        
        cursor = db_connection.cursor()
        
        # Insert first integration
        cursor.execute("""
            INSERT INTO tenant_integrations (tenant_id, integration_type, enabled, config)
            VALUES (?, ?, ?, ?)
        """, (tenant_id, 'slack', 1, '{}'))
        db_connection.commit()
        
        # Attempt to insert duplicate
        with pytest.raises(sqlite3.IntegrityError, match="UNIQUE constraint failed"):
            cursor.execute("""
                INSERT INTO tenant_integrations (tenant_id, integration_type, enabled, config)
                VALUES (?, ?, ?, ?)
            """, (tenant_id, 'slack', 1, '{}'))
            db_connection.commit()


# ============================================================================
# Additional Integration Tests
# ============================================================================

@pytest.mark.unit
class TestIntegrationBasics:
    """Basic unit tests for tenant integrations."""
    
    def test_enable_disable_integration(self, create_tenant, db_connection):
        """Verify enabling and disabling integrations."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        
        integrations = {
            'slack': {'enabled': True, 'config': {'token': 'test'}}
        }
        
        tenant_id = create_tenant(api_key=api_key, integrations=integrations)
        
        # Verify enabled
        tenant = get_tenant_by_api_key(api_key)
        assert tenant.has_integration('slack') is True
        
        # Disable integration
        cursor = db_connection.cursor()
        cursor.execute("""
            UPDATE tenant_integrations SET enabled = 0 
            WHERE tenant_id = ? AND integration_type = ?
        """, (tenant_id, 'slack'))
        db_connection.commit()
        clear_tenant_cache()
        
        # Verify disabled
        tenant_after = get_tenant_by_api_key(api_key)
        assert tenant_after.has_integration('slack') is False
    
    def test_update_integration_config(self, create_tenant, db_connection):
        """Verify updating integration configuration."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        
        initial_config = {'token': 'old_token', 'channel': '#old'}
        integrations = {
            'slack': {'enabled': True, 'config': initial_config}
        }
        
        tenant_id = create_tenant(api_key=api_key, integrations=integrations)
        
        # Update config
        new_config = {'token': 'new_token', 'channel': '#new'}
        cursor = db_connection.cursor()
        cursor.execute("""
            UPDATE tenant_integrations SET config = ? 
            WHERE tenant_id = ? AND integration_type = ?
        """, (json.dumps(new_config), tenant_id, 'slack'))
        db_connection.commit()
        clear_tenant_cache()
        
        # Verify update
        tenant = get_tenant_by_api_key(api_key)
        integration = tenant.get_integration('slack')
        
        assert integration['config'] == new_config
    
    def test_delete_integration(self, create_tenant, db_connection):
        """Verify deleting an integration."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        
        integrations = {
            'slack': {'enabled': True, 'config': {'token': 'test'}}
        }
        
        tenant_id = create_tenant(api_key=api_key, integrations=integrations)
        
        # Verify integration exists
        tenant = get_tenant_by_api_key(api_key)
        assert tenant.has_integration('slack') is True
        
        # Delete integration
        cursor = db_connection.cursor()
        cursor.execute("""
            DELETE FROM tenant_integrations 
            WHERE tenant_id = ? AND integration_type = ?
        """, (tenant_id, 'slack'))
        db_connection.commit()
        clear_tenant_cache()
        
        # Verify deleted
        tenant_after = get_tenant_by_api_key(api_key)
        assert tenant_after.get_integration('slack') is None
    
    def test_integrations_lazy_loading(self, create_tenant, sample_integration_config):
        """Verify that integrations are lazy loaded."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        create_tenant(api_key=api_key, integrations=sample_integration_config)
        
        tenant = get_tenant_by_api_key(api_key)
        
        # Before accessing, should not be loaded
        assert tenant._integrations is None
        
        # After accessing, should be loaded
        integrations = tenant.integrations
        assert tenant._integrations is not None
        assert integrations == tenant._integrations
    
    def test_multiple_tenants_different_integrations(self, create_tenant):
        """Verify that different tenants can have different integrations."""
        # Tenant 1: Only Slack
        api_key1 = f'prm_{secrets.token_urlsafe(32)}'
        create_tenant(api_key=api_key1, integrations={
            'slack': {'enabled': True, 'config': {'token': 'token1'}}
        })
        
        # Tenant 2: Only Sheets
        api_key2 = f'prm_{secrets.token_urlsafe(32)}'
        create_tenant(api_key=api_key2, integrations={
            'sheets': {'enabled': True, 'config': {'sheet_id': 'sheet2'}}
        })
        
        # Verify each tenant has only their integrations
        tenant1 = get_tenant_by_api_key(api_key1)
        tenant2 = get_tenant_by_api_key(api_key2)
        
        assert tenant1.has_integration('slack') is True
        assert tenant1.has_integration('sheets') is False
        
        assert tenant2.has_integration('slack') is False
        assert tenant2.has_integration('sheets') is True
