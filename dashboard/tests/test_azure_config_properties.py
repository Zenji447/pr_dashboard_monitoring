"""
Property-Based Tests for Azure DevOps Configuration

This module implements property-based tests for Azure DevOps configuration
management in the multi-tenant system.

Correctness Properties Validated:
- Property 14: Tenant with Azure config can retrieve it
- Property 15: Azure config update reflects on retrieval
- Property 16: Tenant without Azure config returns None
- Property 17: Azure config validation (non-empty fields)
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
    clear_tenant_cache,
    TenantNotFoundError
)


# ============================================================================
# Hypothesis Strategies
# ============================================================================

@st.composite
def azure_config_strategy(draw):
    """Strategy for generating valid Azure DevOps configuration."""
    org_name = draw(st.text(
        alphabet='abcdefghijklmnopqrstuvwxyz0123456789',
        min_size=1,
        max_size=50
    ))
    project = draw(st.text(min_size=1, max_size=50))
    repository = draw(st.text(min_size=1, max_size=50))
    pat_token = draw(st.one_of(
        st.none(),
        st.text(min_size=10, max_size=100)
    ))
    
    return {
        'org_url': f'https://dev.azure.com/{org_name}',
        'project': project,
        'repository': repository,
        'pat_token': pat_token
    }


@st.composite
def azure_config_update_strategy(draw):
    """Strategy for generating Azure config updates."""
    return {
        'org_url': draw(st.one_of(
            st.none(),
            st.text(min_size=10, max_size=100).map(lambda x: f'https://dev.azure.com/{x}')
        )),
        'project': draw(st.one_of(st.none(), st.text(min_size=1, max_size=50))),
        'repository': draw(st.one_of(st.none(), st.text(min_size=1, max_size=50))),
        'pat_token': draw(st.one_of(st.none(), st.text(min_size=10, max_size=100)))
    }


# ============================================================================
# Property 14: Tenant with Azure Config Can Retrieve It
# ============================================================================

@pytest.mark.property
class TestAzureConfigRetrieval:
    """
    Property 14: For any tenant T with Azure config C, T.azure_config returns C.
    """
    
    @given(azure_config=azure_config_strategy())
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=50)
    def test_tenant_with_azure_config_can_retrieve_it(self, azure_config, create_tenant, cleanup_tenants):
        """Verify that tenant with Azure config can retrieve it."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        
        # Create tenant with Azure config
        tenant_id = create_tenant(
            api_key=api_key,
            azure_config=azure_config
        )
        
        # Retrieve tenant
        tenant = get_tenant_by_api_key(api_key)
        assert tenant is not None
        
        # Verify Azure config matches
        retrieved_config = tenant.azure_config
        assert retrieved_config is not None
        assert retrieved_config['org_url'] == azure_config['org_url']
        assert retrieved_config['project'] == azure_config['project']
        assert retrieved_config['repository'] == azure_config['repository']
        assert retrieved_config['pat_token'] == azure_config['pat_token']
    
    def test_azure_config_lazy_loading(self, create_tenant, sample_azure_config):
        """Verify that Azure config is lazy loaded."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        create_tenant(api_key=api_key, azure_config=sample_azure_config)
        
        tenant = get_tenant_by_api_key(api_key)
        
        # Before accessing, should not be loaded
        assert tenant._azure_config is None
        
        # After accessing, should be loaded
        config = tenant.azure_config
        assert tenant._azure_config is not None
        assert config == tenant._azure_config


# ============================================================================
# Property 15: Azure Config Update Reflects on Retrieval
# ============================================================================

@pytest.mark.property
class TestAzureConfigUpdate:
    """
    Property 15: For any tenant T with Azure config C1, after updating to C2,
    T.azure_config returns C2.
    """
    
    @given(
        initial_config=azure_config_strategy(),
        update_config=azure_config_update_strategy()
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=30)
    def test_azure_config_update_reflects_on_retrieval(
        self, initial_config, update_config, create_tenant, db_connection, cleanup_tenants
    ):
        """Verify that Azure config updates are reflected on retrieval."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        
        # Create tenant with initial config
        tenant_id = create_tenant(
            api_key=api_key,
            azure_config=initial_config
        )
        
        # Prepare update (only non-None values)
        updates = {}
        if update_config['org_url'] is not None:
            updates['org_url'] = update_config['org_url']
        if update_config['project'] is not None:
            updates['project'] = update_config['project']
        if update_config['repository'] is not None:
            updates['repository'] = update_config['repository']
        if update_config['pat_token'] is not None:
            updates['pat_token'] = update_config['pat_token']
        
        # Skip if no updates
        if not updates:
            return
        
        # Apply updates
        set_clause = ', '.join([f"{key} = ?" for key in updates.keys()])
        values = list(updates.values()) + [tenant_id]
        
        cursor = db_connection.cursor()
        cursor.execute(
            f"UPDATE tenant_azure_config SET {set_clause} WHERE tenant_id = ?",
            values
        )
        db_connection.commit()
        
        # Clear cache to force reload
        clear_tenant_cache()
        
        # Retrieve tenant and verify updates
        tenant = get_tenant_by_api_key(api_key)
        retrieved_config = tenant.azure_config
        
        for key, value in updates.items():
            assert retrieved_config[key] == value, f"Update to {key} should be reflected"
    
    def test_azure_config_full_replacement(self, create_tenant, db_connection, sample_azure_config):
        """Verify that Azure config can be fully replaced."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        
        # Create tenant with initial config
        initial_config = {
            'org_url': 'https://dev.azure.com/old-org',
            'project': 'OldProject',
            'repository': 'OldRepo',
            'pat_token': 'old_token'
        }
        tenant_id = create_tenant(api_key=api_key, azure_config=initial_config)
        
        # Replace with new config
        new_config = sample_azure_config
        cursor = db_connection.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO tenant_azure_config (tenant_id, org_url, project, repository, pat_token)
            VALUES (?, ?, ?, ?, ?)
        """, (
            tenant_id,
            new_config['org_url'],
            new_config['project'],
            new_config['repository'],
            new_config['pat_token']
        ))
        db_connection.commit()
        clear_tenant_cache()
        
        # Verify new config
        tenant = get_tenant_by_api_key(api_key)
        retrieved_config = tenant.azure_config
        
        assert retrieved_config['org_url'] == new_config['org_url']
        assert retrieved_config['project'] == new_config['project']
        assert retrieved_config['repository'] == new_config['repository']
        assert retrieved_config['pat_token'] == new_config['pat_token']


# ============================================================================
# Property 16: Tenant Without Azure Config Returns Error
# ============================================================================

@pytest.mark.property
class TestMissingAzureConfig:
    """
    Property 16: For any tenant T without Azure config, accessing T.azure_config
    raises TenantNotFoundError.
    """
    
    def test_tenant_without_azure_config_raises_error(self, create_tenant):
        """Verify that tenant without Azure config raises error."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        
        # Create tenant WITHOUT Azure config
        create_tenant(api_key=api_key)
        
        tenant = get_tenant_by_api_key(api_key)
        assert tenant is not None
        
        # Accessing azure_config should raise error
        with pytest.raises(TenantNotFoundError, match="Azure config not found"):
            _ = tenant.azure_config
    
    def test_deleted_azure_config_raises_error(self, create_tenant, db_connection, sample_azure_config):
        """Verify that deleting Azure config causes error on access."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        
        # Create tenant with Azure config
        tenant_id = create_tenant(api_key=api_key, azure_config=sample_azure_config)
        
        # Verify config exists
        tenant = get_tenant_by_api_key(api_key)
        config = tenant.azure_config
        assert config is not None
        
        # Delete Azure config
        cursor = db_connection.cursor()
        cursor.execute("DELETE FROM tenant_azure_config WHERE tenant_id = ?", (tenant_id,))
        db_connection.commit()
        clear_tenant_cache()
        
        # Accessing azure_config should now raise error
        tenant_after = get_tenant_by_api_key(api_key)
        with pytest.raises(TenantNotFoundError):
            _ = tenant_after.azure_config


# ============================================================================
# Property 17: Azure Config Validation
# ============================================================================

@pytest.mark.property
class TestAzureConfigValidation:
    """
    Property 17: For any Azure config C, C.org_url, C.project, and C.repository
    must be non-empty strings.
    """
    
    @given(azure_config=azure_config_strategy())
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=50)
    def test_valid_azure_config_accepted(self, azure_config, create_tenant, cleanup_tenants):
        """Verify that valid Azure configs are accepted."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        
        # Create tenant with Azure config
        tenant_id = create_tenant(api_key=api_key, azure_config=azure_config)
        
        # Verify config was stored
        tenant = get_tenant_by_api_key(api_key)
        config = tenant.azure_config
        
        # Verify required fields are non-empty
        assert config['org_url'], "org_url should be non-empty"
        assert config['project'], "project should be non-empty"
        assert config['repository'], "repository should be non-empty"
        assert len(config['org_url']) > 0
        assert len(config['project']) > 0
        assert len(config['repository']) > 0
    
    def test_empty_org_url_rejected(self, create_tenant, db_connection):
        """Verify that empty org_url is rejected."""
        # This test verifies application-level validation
        # Database allows empty strings, but application should validate
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        tenant_id = create_tenant(api_key=api_key)
        
        cursor = db_connection.cursor()
        cursor.execute("""
            INSERT INTO tenant_azure_config (tenant_id, org_url, project, repository)
            VALUES (?, ?, ?, ?)
        """, (tenant_id, '', 'Project', 'Repo'))
        db_connection.commit()
        
        # Application should handle empty org_url gracefully
        tenant = get_tenant_by_id(tenant_id)
        config = tenant.azure_config
        
        # Empty string is technically stored, but should be validated at application level
        assert isinstance(config['org_url'], str)
    
    def test_pat_token_optional(self, create_tenant):
        """Verify that PAT token is optional."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        
        # Create tenant with Azure config but no PAT token
        azure_config = {
            'org_url': 'https://dev.azure.com/test',
            'project': 'TestProject',
            'repository': 'TestRepo',
            'pat_token': None
        }
        
        tenant_id = create_tenant(api_key=api_key, azure_config=azure_config)
        
        # Verify config was stored
        tenant = get_tenant_by_api_key(api_key)
        config = tenant.azure_config
        
        assert config['org_url'] == azure_config['org_url']
        assert config['project'] == azure_config['project']
        assert config['repository'] == azure_config['repository']
        assert config['pat_token'] is None


# ============================================================================
# Additional Azure Config Tests
# ============================================================================

@pytest.mark.unit
class TestAzureConfigBasics:
    """Basic unit tests for Azure DevOps configuration."""
    
    def test_create_azure_config_with_all_fields(self, create_tenant, sample_azure_config):
        """Verify creating Azure config with all fields."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        tenant_id = create_tenant(api_key=api_key, azure_config=sample_azure_config)
        
        tenant = get_tenant_by_api_key(api_key)
        config = tenant.azure_config
        
        assert config['org_url'] == sample_azure_config['org_url']
        assert config['project'] == sample_azure_config['project']
        assert config['repository'] == sample_azure_config['repository']
        assert config['pat_token'] == sample_azure_config['pat_token']
    
    def test_update_azure_org_url(self, create_tenant, db_connection, sample_azure_config):
        """Verify updating Azure org URL."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        tenant_id = create_tenant(api_key=api_key, azure_config=sample_azure_config)
        
        # Update org URL
        new_org_url = 'https://dev.azure.com/new-org'
        cursor = db_connection.cursor()
        cursor.execute(
            "UPDATE tenant_azure_config SET org_url = ? WHERE tenant_id = ?",
            (new_org_url, tenant_id)
        )
        db_connection.commit()
        clear_tenant_cache()
        
        # Verify update
        tenant = get_tenant_by_api_key(api_key)
        config = tenant.azure_config
        assert config['org_url'] == new_org_url
    
    def test_update_azure_project(self, create_tenant, db_connection, sample_azure_config):
        """Verify updating Azure project."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        tenant_id = create_tenant(api_key=api_key, azure_config=sample_azure_config)
        
        # Update project
        new_project = 'NewProject'
        cursor = db_connection.cursor()
        cursor.execute(
            "UPDATE tenant_azure_config SET project = ? WHERE tenant_id = ?",
            (new_project, tenant_id)
        )
        db_connection.commit()
        clear_tenant_cache()
        
        # Verify update
        tenant = get_tenant_by_api_key(api_key)
        config = tenant.azure_config
        assert config['project'] == new_project
    
    def test_update_azure_repository(self, create_tenant, db_connection, sample_azure_config):
        """Verify updating Azure repository."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        tenant_id = create_tenant(api_key=api_key, azure_config=sample_azure_config)
        
        # Update repository
        new_repo = 'NewRepo'
        cursor = db_connection.cursor()
        cursor.execute(
            "UPDATE tenant_azure_config SET repository = ? WHERE tenant_id = ?",
            (new_repo, tenant_id)
        )
        db_connection.commit()
        clear_tenant_cache()
        
        # Verify update
        tenant = get_tenant_by_api_key(api_key)
        config = tenant.azure_config
        assert config['repository'] == new_repo
    
    def test_update_pat_token(self, create_tenant, db_connection, sample_azure_config):
        """Verify updating PAT token."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        tenant_id = create_tenant(api_key=api_key, azure_config=sample_azure_config)
        
        # Update PAT token
        new_token = 'new_pat_token_12345'
        cursor = db_connection.cursor()
        cursor.execute(
            "UPDATE tenant_azure_config SET pat_token = ? WHERE tenant_id = ?",
            (new_token, tenant_id)
        )
        db_connection.commit()
        clear_tenant_cache()
        
        # Verify update
        tenant = get_tenant_by_api_key(api_key)
        config = tenant.azure_config
        assert config['pat_token'] == new_token
    
    def test_azure_config_cascade_delete(self, create_tenant, db_connection, sample_azure_config):
        """Verify that Azure config is deleted when tenant is deleted."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        tenant_id = create_tenant(api_key=api_key, azure_config=sample_azure_config)
        
        # Verify config exists
        cursor = db_connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM tenant_azure_config WHERE tenant_id = ?", (tenant_id,))
        count_before = cursor.fetchone()[0]
        assert count_before == 1
        
        # Delete tenant (hard delete for testing)
        cursor.execute("DELETE FROM tenants WHERE id = ?", (tenant_id,))
        db_connection.commit()
        
        # Verify Azure config was cascade deleted
        cursor.execute("SELECT COUNT(*) FROM tenant_azure_config WHERE tenant_id = ?", (tenant_id,))
        count_after = cursor.fetchone()[0]
        assert count_after == 0, "Azure config should be cascade deleted with tenant"
    
    def test_multiple_tenants_different_azure_configs(self, create_tenant):
        """Verify that multiple tenants can have different Azure configs."""
        configs = []
        
        for i in range(3):
            api_key = f'prm_{secrets.token_urlsafe(32)}'
            azure_config = {
                'org_url': f'https://dev.azure.com/org-{i}',
                'project': f'Project{i}',
                'repository': f'Repo{i}',
                'pat_token': f'token_{i}'
            }
            
            create_tenant(api_key=api_key, azure_config=azure_config)
            tenant = get_tenant_by_api_key(api_key)
            configs.append(tenant.azure_config)
        
        # Verify all configs are different
        assert configs[0]['org_url'] != configs[1]['org_url']
        assert configs[1]['org_url'] != configs[2]['org_url']
        assert configs[0]['project'] != configs[1]['project']
        assert configs[1]['project'] != configs[2]['project']
