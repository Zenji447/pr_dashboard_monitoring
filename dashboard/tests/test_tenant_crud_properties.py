"""
Property-Based Tests for Tenant CRUD Operations

This module implements property-based tests for tenant creation, retrieval,
update, and deletion operations.

Correctness Properties Validated:
- Property 6: Created tenant can be retrieved by ID
- Property 7: Created tenant can be retrieved by API Key
- Property 8: Subdomain uniqueness constraint enforced
- Property 9: Plan validation (basic/pro/enterprise only)
- Property 10: Status validation (active/inactive only)
- Property 11: Soft delete preserves data
- Property 12: Updated tenant reflects changes on retrieval
- Property 13: API Key regeneration invalidates old key
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
def valid_subdomain_strategy(draw):
    """Strategy for generating valid subdomains."""
    # Subdomain: lowercase, alphanumeric with hyphens, 3-20 chars
    subdomain = draw(st.text(
        alphabet='abcdefghijklmnopqrstuvwxyz0123456789-',
        min_size=3,
        max_size=20
    ).filter(lambda x: x and not x.startswith('-') and not x.endswith('-') and '--' not in x))
    return subdomain


@st.composite
def tenant_create_data_strategy(draw):
    """Strategy for generating valid tenant creation data."""
    return {
        'subdomain': draw(valid_subdomain_strategy()),
        'company_name': draw(st.text(min_size=1, max_size=100)),
        'plan': draw(st.sampled_from(['basic', 'pro', 'enterprise'])),
    }


@st.composite
def tenant_update_data_strategy(draw):
    """Strategy for generating valid tenant update data."""
    return {
        'company_name': draw(st.one_of(st.none(), st.text(min_size=1, max_size=100))),
        'plan': draw(st.one_of(st.none(), st.sampled_from(['basic', 'pro', 'enterprise']))),
        'status': draw(st.one_of(st.none(), st.sampled_from(['active', 'inactive']))),
    }


# ============================================================================
# Property 6: Created Tenant Can Be Retrieved by ID
# ============================================================================

@pytest.mark.property
class TestTenantCreationAndRetrieval:
    """
    Property 6: For any valid tenant data D, after creating a tenant with D,
    get_tenant_by_id(tenant_id) returns a tenant with the same data.
    """
    
    @given(tenant_data=tenant_create_data_strategy())
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=50)
    def test_created_tenant_retrievable_by_id(self, tenant_data, create_tenant, cleanup_tenants):
        """Verify that a created tenant can be retrieved by its ID."""
        # Create tenant with unique subdomain
        unique_subdomain = f"{tenant_data['subdomain']}-{secrets.token_hex(4)}"
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        
        tenant_id = create_tenant(
            subdomain=unique_subdomain,
            company_name=tenant_data['company_name'],
            api_key=api_key,
            plan=tenant_data['plan'],
            status='active'
        )
        
        # Retrieve tenant by ID
        tenant = get_tenant_by_id(tenant_id)
        
        # Verify tenant data matches
        assert tenant is not None, "Created tenant should be retrievable by ID"
        assert tenant.id == tenant_id
        assert tenant.subdomain == unique_subdomain
        assert tenant.company_name == tenant_data['company_name']
        assert tenant.plan == tenant_data['plan']
        assert tenant.status == 'active'
    
    def test_nonexistent_tenant_id_returns_none(self):
        """Verify that retrieving a non-existent tenant ID returns None."""
        tenant = get_tenant_by_id(999999)
        assert tenant is None, "Non-existent tenant ID should return None"


# ============================================================================
# Property 7: Created Tenant Can Be Retrieved by API Key
# ============================================================================

@pytest.mark.property
class TestTenantRetrievalByAPIKey:
    """
    Property 7: For any valid tenant data D with API Key K, after creating
    a tenant, get_tenant_by_api_key(K) returns the tenant.
    """
    
    @given(tenant_data=tenant_create_data_strategy())
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=50)
    def test_created_tenant_retrievable_by_api_key(self, tenant_data, create_tenant, cleanup_tenants):
        """Verify that a created tenant can be retrieved by its API Key."""
        unique_subdomain = f"{tenant_data['subdomain']}-{secrets.token_hex(4)}"
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        
        tenant_id = create_tenant(
            subdomain=unique_subdomain,
            company_name=tenant_data['company_name'],
            api_key=api_key,
            plan=tenant_data['plan'],
            status='active'
        )
        
        # Clear cache to force database lookup
        clear_tenant_cache()
        
        # Retrieve tenant by API Key
        tenant = get_tenant_by_api_key(api_key)
        
        # Verify tenant data matches
        assert tenant is not None, "Created tenant should be retrievable by API Key"
        assert tenant.id == tenant_id
        assert tenant.api_key == api_key
        assert tenant.subdomain == unique_subdomain
        assert tenant.company_name == tenant_data['company_name']


# ============================================================================
# Property 8: Subdomain Uniqueness Constraint
# ============================================================================

@pytest.mark.property
class TestSubdomainUniqueness:
    """
    Property 8: For any subdomain S, attempting to create two tenants with
    the same subdomain S results in a constraint violation.
    """
    
    def test_duplicate_subdomain_rejected(self, create_tenant, db_connection):
        """Verify that duplicate subdomains are rejected by the database."""
        subdomain = f'test-{secrets.token_hex(4)}'
        
        # Create first tenant
        create_tenant(subdomain=subdomain)
        
        # Attempt to create second tenant with same subdomain
        with pytest.raises(sqlite3.IntegrityError, match="UNIQUE constraint failed.*subdomain"):
            cursor = db_connection.cursor()
            cursor.execute("""
                INSERT INTO tenants (subdomain, company_name, api_key, plan, status)
                VALUES (?, ?, ?, ?, ?)
            """, (subdomain, 'Another Company', f'prm_{secrets.token_urlsafe(32)}', 'basic', 'active'))
            db_connection.commit()
    
    @given(subdomain=valid_subdomain_strategy())
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=30)
    def test_subdomain_uniqueness_property(self, subdomain, create_tenant, cleanup_tenants):
        """Property test: subdomains must be unique across all tenants."""
        unique_subdomain = f"{subdomain}-{secrets.token_hex(4)}"
        
        # Create first tenant
        tenant_id1 = create_tenant(subdomain=unique_subdomain)
        
        # Verify first tenant exists
        tenant1 = get_tenant_by_id(tenant_id1)
        assert tenant1 is not None
        assert tenant1.subdomain == unique_subdomain


# ============================================================================
# Property 9: Plan Validation
# ============================================================================

@pytest.mark.property
class TestPlanValidation:
    """
    Property 9: For any tenant T, T.plan must be one of: basic, pro, enterprise.
    """
    
    @given(plan=st.sampled_from(['basic', 'pro', 'enterprise']))
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=20)
    def test_valid_plans_accepted(self, plan, create_tenant, cleanup_tenants):
        """Verify that valid plans are accepted."""
        tenant_id = create_tenant(plan=plan)
        tenant = get_tenant_by_id(tenant_id)
        
        assert tenant is not None
        assert tenant.plan == plan
        assert tenant.plan in ['basic', 'pro', 'enterprise']
    
    def test_invalid_plan_rejected(self, db_connection):
        """Verify that invalid plans are rejected by the database."""
        with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
            cursor = db_connection.cursor()
            cursor.execute("""
                INSERT INTO tenants (subdomain, company_name, api_key, plan, status)
                VALUES (?, ?, ?, ?, ?)
            """, (
                f'test-{secrets.token_hex(4)}',
                'Test Company',
                f'prm_{secrets.token_urlsafe(32)}',
                'invalid_plan',  # Invalid plan
                'active'
            ))
            db_connection.commit()


# ============================================================================
# Property 10: Status Validation
# ============================================================================

@pytest.mark.property
class TestStatusValidation:
    """
    Property 10: For any tenant T, T.status must be one of: active, inactive.
    """
    
    @given(status=st.sampled_from(['active', 'inactive']))
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=20)
    def test_valid_status_accepted(self, status, create_tenant, cleanup_tenants):
        """Verify that valid status values are accepted."""
        tenant_id = create_tenant(status=status)
        tenant = get_tenant_by_id(tenant_id)
        
        assert tenant is not None
        assert tenant.status == status
        assert tenant.status in ['active', 'inactive']
    
    def test_invalid_status_rejected(self, db_connection):
        """Verify that invalid status values are rejected by the database."""
        with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
            cursor = db_connection.cursor()
            cursor.execute("""
                INSERT INTO tenants (subdomain, company_name, api_key, plan, status)
                VALUES (?, ?, ?, ?, ?)
            """, (
                f'test-{secrets.token_hex(4)}',
                'Test Company',
                f'prm_{secrets.token_urlsafe(32)}',
                'basic',
                'invalid_status'  # Invalid status
            ))
            db_connection.commit()


# ============================================================================
# Property 11: Soft Delete Preserves Data
# ============================================================================

@pytest.mark.property
class TestSoftDelete:
    """
    Property 11: For any tenant T, after soft delete (status='inactive'),
    the tenant data is preserved and can still be retrieved by ID.
    """
    
    @given(tenant_data=tenant_create_data_strategy())
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=30)
    def test_soft_delete_preserves_data(self, tenant_data, create_tenant, db_connection, cleanup_tenants):
        """Verify that soft delete preserves tenant data."""
        unique_subdomain = f"{tenant_data['subdomain']}-{secrets.token_hex(4)}"
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        
        # Create tenant
        tenant_id = create_tenant(
            subdomain=unique_subdomain,
            company_name=tenant_data['company_name'],
            api_key=api_key,
            plan=tenant_data['plan'],
            status='active'
        )
        
        # Verify tenant is active
        tenant_before = get_tenant_by_id(tenant_id)
        assert tenant_before is not None
        assert tenant_before.status == 'active'
        
        # Soft delete (set status to inactive)
        cursor = db_connection.cursor()
        cursor.execute("UPDATE tenants SET status = 'inactive' WHERE id = ?", (tenant_id,))
        db_connection.commit()
        
        # Clear cache
        clear_tenant_cache()
        
        # Verify tenant data is preserved (can still retrieve by ID)
        cursor.execute("SELECT * FROM tenants WHERE id = ?", (tenant_id,))
        row = cursor.fetchone()
        assert row is not None, "Soft deleted tenant data should be preserved"
        
        # Verify all data is intact
        tenant_dict = dict(zip([desc[0] for desc in cursor.description], row))
        assert tenant_dict['id'] == tenant_id
        assert tenant_dict['subdomain'] == unique_subdomain
        assert tenant_dict['company_name'] == tenant_data['company_name']
        assert tenant_dict['api_key'] == api_key
        assert tenant_dict['plan'] == tenant_data['plan']
        assert tenant_dict['status'] == 'inactive'
    
    def test_soft_deleted_tenant_not_retrievable_by_api_key(self, create_tenant, db_connection):
        """Verify that soft deleted tenants cannot be retrieved by API Key."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        tenant_id = create_tenant(api_key=api_key, status='active')
        
        # Verify tenant is retrievable when active
        tenant = get_tenant_by_api_key(api_key)
        assert tenant is not None
        
        # Soft delete
        cursor = db_connection.cursor()
        cursor.execute("UPDATE tenants SET status = 'inactive' WHERE id = ?", (tenant_id,))
        db_connection.commit()
        clear_tenant_cache()
        
        # Verify tenant is NOT retrievable by API Key when inactive
        tenant_after = get_tenant_by_api_key(api_key)
        assert tenant_after is None, "Inactive tenant should not be retrievable by API Key"


# ============================================================================
# Property 12: Updated Tenant Reflects Changes
# ============================================================================

@pytest.mark.property
class TestTenantUpdate:
    """
    Property 12: For any tenant T and update data U, after updating T with U,
    retrieving T returns the updated data.
    """
    
    @given(
        initial_data=tenant_create_data_strategy(),
        update_data=tenant_update_data_strategy()
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=30)
    def test_tenant_update_reflects_changes(self, initial_data, update_data, create_tenant, db_connection, cleanup_tenants):
        """Verify that tenant updates are reflected on retrieval."""
        unique_subdomain = f"{initial_data['subdomain']}-{secrets.token_hex(4)}"
        
        # Create tenant
        tenant_id = create_tenant(
            subdomain=unique_subdomain,
            company_name=initial_data['company_name'],
            plan=initial_data['plan'],
            status='active'
        )
        
        # Prepare update
        updates = {}
        if update_data['company_name'] is not None:
            updates['company_name'] = update_data['company_name']
        if update_data['plan'] is not None:
            updates['plan'] = update_data['plan']
        if update_data['status'] is not None:
            updates['status'] = update_data['status']
        
        # Skip if no updates
        if not updates:
            return
        
        # Apply updates
        set_clause = ', '.join([f"{key} = ?" for key in updates.keys()])
        values = list(updates.values()) + [tenant_id]
        
        cursor = db_connection.cursor()
        cursor.execute(f"UPDATE tenants SET {set_clause} WHERE id = ?", values)
        db_connection.commit()
        
        # Clear cache
        clear_tenant_cache()
        
        # Retrieve updated tenant
        cursor.execute("SELECT * FROM tenants WHERE id = ?", (tenant_id,))
        row = cursor.fetchone()
        tenant_dict = dict(zip([desc[0] for desc in cursor.description], row))
        
        # Verify updates were applied
        for key, value in updates.items():
            assert tenant_dict[key] == value, f"Update to {key} should be reflected"


# ============================================================================
# Property 13: API Key Regeneration Invalidates Old Key
# ============================================================================

@pytest.mark.property
class TestAPIKeyRegeneration:
    """
    Property 13: For any tenant T with API Key K1, after regenerating the
    API Key to K2, K1 no longer retrieves T and K2 retrieves T.
    """
    
    @given(tenant_data=tenant_create_data_strategy())
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=30)
    def test_api_key_regeneration_invalidates_old_key(self, tenant_data, create_tenant, db_connection, cleanup_tenants):
        """Verify that API Key regeneration invalidates the old key."""
        unique_subdomain = f"{tenant_data['subdomain']}-{secrets.token_hex(4)}"
        old_api_key = f'prm_{secrets.token_urlsafe(32)}'
        
        # Create tenant
        tenant_id = create_tenant(
            subdomain=unique_subdomain,
            company_name=tenant_data['company_name'],
            api_key=old_api_key,
            plan=tenant_data['plan'],
            status='active'
        )
        
        # Verify old key works
        tenant_before = get_tenant_by_api_key(old_api_key)
        assert tenant_before is not None
        assert tenant_before.id == tenant_id
        
        # Generate new API Key
        new_api_key = f'prm_{secrets.token_urlsafe(32)}'
        
        # Update API Key
        cursor = db_connection.cursor()
        cursor.execute("UPDATE tenants SET api_key = ? WHERE id = ?", (new_api_key, tenant_id))
        db_connection.commit()
        
        # Clear cache
        clear_tenant_cache()
        
        # Verify old key no longer works
        tenant_with_old_key = get_tenant_by_api_key(old_api_key)
        assert tenant_with_old_key is None, "Old API Key should not retrieve tenant"
        
        # Verify new key works
        tenant_with_new_key = get_tenant_by_api_key(new_api_key)
        assert tenant_with_new_key is not None, "New API Key should retrieve tenant"
        assert tenant_with_new_key.id == tenant_id
        assert tenant_with_new_key.api_key == new_api_key
    
    def test_api_key_regeneration_uniqueness(self, create_tenant, db_connection):
        """Verify that regenerated API Keys are unique."""
        # Create tenant
        tenant_id = create_tenant()
        
        # Generate multiple new API Keys
        api_keys = set()
        for _ in range(100):
            new_key = f'prm_{secrets.token_urlsafe(32)}'
            api_keys.add(new_key)
        
        # All keys should be unique
        assert len(api_keys) == 100, "Generated API Keys should be unique"


# ============================================================================
# Additional CRUD Tests
# ============================================================================

@pytest.mark.unit
class TestTenantCRUDBasics:
    """Basic unit tests for tenant CRUD operations."""
    
    def test_create_tenant_with_all_fields(self, create_tenant, sample_azure_config, sample_integration_config):
        """Verify creating a tenant with all fields."""
        tenant_id = create_tenant(
            subdomain='full-test',
            company_name='Full Test Company',
            plan='enterprise',
            status='active',
            azure_config=sample_azure_config,
            integrations=sample_integration_config,
            settings={
                'language': 'en',
                'timezone': 'America/New_York'
            }
        )
        
        tenant = get_tenant_by_id(tenant_id)
        assert tenant is not None
        assert tenant.subdomain == 'full-test'
        assert tenant.company_name == 'Full Test Company'
        assert tenant.plan == 'enterprise'
        
        # Verify Azure config
        assert tenant.azure_config is not None
        assert tenant.azure_config['org_url'] == sample_azure_config['org_url']
        
        # Verify integrations
        assert tenant.has_integration('slack')
        assert tenant.has_integration('sheets')
        
        # Verify settings
        assert tenant.settings['language'] == 'en'
        assert tenant.settings['timezone'] == 'America/New_York'
    
    def test_create_minimal_tenant(self, create_tenant):
        """Verify creating a tenant with minimal required fields."""
        tenant_id = create_tenant(
            subdomain='minimal-test',
            company_name='Minimal Company'
        )
        
        tenant = get_tenant_by_id(tenant_id)
        assert tenant is not None
        assert tenant.subdomain == 'minimal-test'
        assert tenant.company_name == 'Minimal Company'
        assert tenant.plan == 'basic'  # Default
        assert tenant.status == 'active'  # Default
    
    def test_update_tenant_company_name(self, create_tenant, db_connection):
        """Verify updating tenant company name."""
        tenant_id = create_tenant(company_name='Old Name')
        
        # Update company name
        cursor = db_connection.cursor()
        cursor.execute("UPDATE tenants SET company_name = ? WHERE id = ?", ('New Name', tenant_id))
        db_connection.commit()
        clear_tenant_cache()
        
        # Verify update
        cursor.execute("SELECT company_name FROM tenants WHERE id = ?", (tenant_id,))
        row = cursor.fetchone()
        assert row[0] == 'New Name'
    
    def test_update_tenant_plan(self, create_tenant, db_connection):
        """Verify updating tenant plan."""
        tenant_id = create_tenant(plan='basic')
        
        # Update plan
        cursor = db_connection.cursor()
        cursor.execute("UPDATE tenants SET plan = ? WHERE id = ?", ('enterprise', tenant_id))
        db_connection.commit()
        clear_tenant_cache()
        
        # Verify update
        tenant = get_tenant_by_id(tenant_id)
        assert tenant.plan == 'enterprise'
    
    def test_list_multiple_tenants(self, create_tenant, db_connection):
        """Verify listing multiple tenants."""
        # Create multiple tenants
        tenant_ids = []
        for i in range(5):
            tenant_id = create_tenant(
                subdomain=f'tenant-{i}',
                company_name=f'Company {i}'
            )
            tenant_ids.append(tenant_id)
        
        # List all tenants
        cursor = db_connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM tenants WHERE status = 'active'")
        count = cursor.fetchone()[0]
        
        assert count >= 5, "Should have at least 5 active tenants"
