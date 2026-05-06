"""
Property-Based Tests for Tenant Context Management

This module implements property-based tests using the hypothesis library
to validate the correctness properties defined in the design document.

Correctness Properties Validated:
- Property 1: API Key Uniqueness
- Property 2: Tenant Retrieval Consistency
- Property 3: Cache Consistency
- Property 4: Context Isolation
- Property 5: Lazy Loading Behavior
"""
import secrets
import sqlite3
import threading
import time
from typing import List
import pytest
from hypothesis import given, strategies as st, settings, assume, HealthCheck

from integrations.tenant_context import (
    Tenant,
    get_tenant_by_api_key,
    get_tenant_by_id,
    set_current_tenant,
    get_current_tenant,
    clear_tenant_cache,
    TenantNotFoundError
)


# ============================================================================
# Hypothesis Strategies
# ============================================================================

@st.composite
def tenant_data_strategy(draw):
    """Strategy for generating valid tenant data."""
    subdomain = draw(st.text(
        alphabet=st.characters(whitelist_categories=('Ll', 'Nd'), whitelist_characters='-'),
        min_size=3,
        max_size=20
    ).filter(lambda x: x and not x.startswith('-') and not x.endswith('-')))
    
    company_name = draw(st.text(min_size=1, max_size=100))
    
    plan = draw(st.sampled_from(['basic', 'pro', 'enterprise']))
    
    status = draw(st.sampled_from(['active', 'inactive']))
    
    return {
        'subdomain': subdomain,
        'company_name': company_name,
        'plan': plan,
        'status': status
    }


@st.composite
def azure_config_strategy(draw):
    """Strategy for generating valid Azure DevOps configuration."""
    org_name = draw(st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('L', 'Nd'))))
    project = draw(st.text(min_size=1, max_size=50))
    repository = draw(st.text(min_size=1, max_size=50))
    
    return {
        'org_url': f'https://dev.azure.com/{org_name}',
        'project': project,
        'repository': repository,
        'pat_token': draw(st.one_of(st.none(), st.text(min_size=10, max_size=100)))
    }


# ============================================================================
# Property 1: API Key Uniqueness
# ============================================================================

@pytest.mark.property
class TestAPIKeyUniqueness:
    """
    Property 1: For any set of generated API Keys, all keys must be unique.
    
    This validates that the API Key generation mechanism produces unique keys
    and that the database enforces uniqueness constraints.
    """
    
    def test_generated_api_keys_are_unique(self):
        """Generate multiple API Keys and verify they are all unique."""
        num_keys = 1000
        api_keys = set()
        
        for _ in range(num_keys):
            api_key = f'prm_{secrets.token_urlsafe(32)}'
            api_keys.add(api_key)
        
        # All keys should be unique
        assert len(api_keys) == num_keys, "Generated API Keys are not unique"
    
    def test_database_enforces_api_key_uniqueness(self, db_connection, create_tenant):
        """Verify that the database enforces API Key uniqueness constraint."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        
        # Create first tenant with API Key
        create_tenant(api_key=api_key)
        
        # Attempt to create second tenant with same API Key should fail
        with pytest.raises(sqlite3.IntegrityError):
            cursor = db_connection.cursor()
            cursor.execute("""
                INSERT INTO tenants (subdomain, company_name, api_key, plan, status)
                VALUES (?, ?, ?, ?, ?)
            """, ('another-subdomain', 'Another Company', api_key, 'basic', 'active'))
            db_connection.commit()


# ============================================================================
# Property 2: Tenant Retrieval Consistency
# ============================================================================

@pytest.mark.property
class TestTenantRetrievalConsistency:
    """
    Property 2: For any tenant T with API Key K, get_tenant_by_api_key(K)
    returns T consistently across multiple calls.
    
    This validates that tenant retrieval is deterministic and consistent.
    """
    
    @given(tenant_data=tenant_data_strategy())
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_tenant_retrieval_is_consistent(self, tenant_data, create_tenant):
        """Verify that retrieving a tenant by API Key returns consistent results."""
        # Create tenant
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        tenant_id = create_tenant(
            subdomain=tenant_data['subdomain'],
            company_name=tenant_data['company_name'],
            api_key=api_key,
            plan=tenant_data['plan'],
            status=tenant_data['status']
        )
        
        # Only test active tenants (inactive tenants return None)
        if tenant_data['status'] != 'active':
            return
        
        # Retrieve tenant multiple times
        tenant1 = get_tenant_by_api_key(api_key)
        tenant2 = get_tenant_by_api_key(api_key)
        tenant3 = get_tenant_by_api_key(api_key)
        
        # All retrievals should return the same tenant
        assert tenant1 is not None
        assert tenant2 is not None
        assert tenant3 is not None
        
        assert tenant1.id == tenant_id
        assert tenant2.id == tenant_id
        assert tenant3.id == tenant_id
        
        assert tenant1.subdomain == tenant_data['subdomain']
        assert tenant2.subdomain == tenant_data['subdomain']
        assert tenant3.subdomain == tenant_data['subdomain']
        
        assert tenant1.company_name == tenant_data['company_name']
        assert tenant2.company_name == tenant_data['company_name']
        assert tenant3.company_name == tenant_data['company_name']
    
    def test_inactive_tenant_not_retrievable_by_api_key(self, create_tenant):
        """Verify that inactive tenants cannot be retrieved by API Key."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        create_tenant(api_key=api_key, status='inactive')
        
        tenant = get_tenant_by_api_key(api_key)
        assert tenant is None, "Inactive tenant should not be retrievable by API Key"


# ============================================================================
# Property 3: Cache Consistency
# ============================================================================

@pytest.mark.property
class TestCacheConsistency:
    """
    Property 3: For any tenant T with API Key K, if T is in cache,
    get_tenant_by_api_key(K) returns the same data as a fresh database query.
    
    This validates that the cache maintains consistency with the database.
    """
    
    @given(tenant_data=tenant_data_strategy())
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_cache_returns_same_data_as_database(self, tenant_data, create_tenant):
        """Verify that cached tenant data matches database data."""
        assume(tenant_data['status'] == 'active')
        
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        tenant_id = create_tenant(
            subdomain=tenant_data['subdomain'],
            company_name=tenant_data['company_name'],
            api_key=api_key,
            plan=tenant_data['plan'],
            status=tenant_data['status']
        )
        
        # First call - cache miss, loads from database
        clear_tenant_cache()
        tenant_from_db = get_tenant_by_api_key(api_key)
        
        # Second call - cache hit
        tenant_from_cache = get_tenant_by_api_key(api_key)
        
        # Both should return the same data
        assert tenant_from_db is not None
        assert tenant_from_cache is not None
        
        assert tenant_from_db.id == tenant_from_cache.id == tenant_id
        assert tenant_from_db.subdomain == tenant_from_cache.subdomain == tenant_data['subdomain']
        assert tenant_from_db.company_name == tenant_from_cache.company_name == tenant_data['company_name']
        assert tenant_from_db.plan == tenant_from_cache.plan == tenant_data['plan']
        assert tenant_from_db.status == tenant_from_cache.status == tenant_data['status']
    
    def test_cache_clear_forces_database_reload(self, create_tenant):
        """Verify that clearing cache forces reload from database."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        create_tenant(api_key=api_key, company_name='Original Name')
        
        # Load into cache
        tenant1 = get_tenant_by_api_key(api_key)
        assert tenant1.company_name == 'Original Name'
        
        # Clear cache
        clear_tenant_cache()
        
        # Next retrieval should reload from database
        tenant2 = get_tenant_by_api_key(api_key)
        assert tenant2.company_name == 'Original Name'
        assert tenant1.id == tenant2.id


# ============================================================================
# Property 4: Context Isolation
# ============================================================================

@pytest.mark.property
class TestContextIsolation:
    """
    Property 4: For any two concurrent requests R1 and R2 with tenants T1 and T2,
    the tenant context in R1 does not affect the tenant context in R2.
    
    This validates thread-safety of the tenant context system.
    """
    
    def test_concurrent_requests_maintain_separate_contexts(self, create_tenant):
        """Verify that concurrent threads maintain separate tenant contexts."""
        # Create two tenants
        api_key1 = f'prm_{secrets.token_urlsafe(32)}'
        api_key2 = f'prm_{secrets.token_urlsafe(32)}'
        
        tenant_id1 = create_tenant(api_key=api_key1, company_name='Company 1')
        tenant_id2 = create_tenant(api_key=api_key2, company_name='Company 2')
        
        tenant1 = get_tenant_by_api_key(api_key1)
        tenant2 = get_tenant_by_api_key(api_key2)
        
        results = {'thread1': None, 'thread2': None}
        errors = []
        
        def thread1_work():
            try:
                set_current_tenant(tenant1)
                time.sleep(0.01)  # Simulate work
                current = get_current_tenant()
                results['thread1'] = current.id if current else None
            except Exception as e:
                errors.append(('thread1', e))
        
        def thread2_work():
            try:
                set_current_tenant(tenant2)
                time.sleep(0.01)  # Simulate work
                current = get_current_tenant()
                results['thread2'] = current.id if current else None
            except Exception as e:
                errors.append(('thread2', e))
        
        # Run threads concurrently
        t1 = threading.Thread(target=thread1_work)
        t2 = threading.Thread(target=thread2_work)
        
        t1.start()
        t2.start()
        
        t1.join()
        t2.join()
        
        # Check for errors
        assert len(errors) == 0, f"Errors occurred: {errors}"
        
        # Each thread should have maintained its own tenant context
        assert results['thread1'] == tenant_id1, "Thread 1 lost its tenant context"
        assert results['thread2'] == tenant_id2, "Thread 2 lost its tenant context"
    
    @given(num_threads=st.integers(min_value=2, max_value=10))
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=10)
    def test_multiple_concurrent_contexts(self, num_threads, create_tenant):
        """Verify context isolation with multiple concurrent threads."""
        # Create tenants
        tenants = []
        for i in range(num_threads):
            api_key = f'prm_{secrets.token_urlsafe(32)}'
            tenant_id = create_tenant(api_key=api_key, company_name=f'Company {i}')
            tenant = get_tenant_by_api_key(api_key)
            tenants.append(tenant)
        
        results = {}
        errors = []
        
        def thread_work(thread_id, tenant):
            try:
                set_current_tenant(tenant)
                time.sleep(0.001 * thread_id)  # Stagger execution
                current = get_current_tenant()
                results[thread_id] = current.id if current else None
            except Exception as e:
                errors.append((thread_id, e))
        
        # Run all threads
        threads = []
        for i, tenant in enumerate(tenants):
            t = threading.Thread(target=thread_work, args=(i, tenant))
            threads.append(t)
            t.start()
        
        # Wait for all threads
        for t in threads:
            t.join()
        
        # Verify no errors
        assert len(errors) == 0, f"Errors occurred: {errors}"
        
        # Verify each thread maintained its context
        for i, tenant in enumerate(tenants):
            assert results[i] == tenant.id, f"Thread {i} lost its tenant context"


# ============================================================================
# Property 5: Lazy Loading Behavior
# ============================================================================

@pytest.mark.property
class TestLazyLoadingBehavior:
    """
    Property 5: For any tenant T, accessing T.azure_config, T.integrations,
    or T.settings loads the data only once, and subsequent accesses return
    the cached data without additional database queries.
    
    This validates the lazy loading optimization.
    """
    
    @given(azure_config=azure_config_strategy())
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_azure_config_loaded_only_once(self, azure_config, create_tenant):
        """Verify that Azure config is loaded only once."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        create_tenant(api_key=api_key, azure_config=azure_config)
        
        tenant = get_tenant_by_api_key(api_key)
        
        # First access - should load from database
        assert tenant._azure_config is None, "Azure config should not be loaded yet"
        config1 = tenant.azure_config
        assert tenant._azure_config is not None, "Azure config should be loaded now"
        
        # Second access - should return cached data
        config2 = tenant.azure_config
        
        # Both should be the same object (cached)
        assert config1 is config2, "Azure config should be cached"
        
        # Verify data matches
        assert config1['org_url'] == azure_config['org_url']
        assert config1['project'] == azure_config['project']
        assert config1['repository'] == azure_config['repository']
    
    def test_integrations_loaded_only_once(self, create_tenant, sample_integration_config):
        """Verify that integrations are loaded only once."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        create_tenant(api_key=api_key, integrations=sample_integration_config)
        
        tenant = get_tenant_by_api_key(api_key)
        
        # First access - should load from database
        assert tenant._integrations is None, "Integrations should not be loaded yet"
        integrations1 = tenant.integrations
        assert tenant._integrations is not None, "Integrations should be loaded now"
        
        # Second access - should return cached data
        integrations2 = tenant.integrations
        
        # Both should be the same object (cached)
        assert integrations1 is integrations2, "Integrations should be cached"
    
    def test_settings_loaded_only_once(self, create_tenant):
        """Verify that settings are loaded only once."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        settings_data = {
            'language': 'en',
            'timezone': 'America/New_York',
            'blocked_authors': ['user1', 'user2'],
            'blocked_branches': ['temp/*']
        }
        create_tenant(api_key=api_key, settings=settings_data)
        
        tenant = get_tenant_by_api_key(api_key)
        
        # First access - should load from database
        assert tenant._settings is None, "Settings should not be loaded yet"
        settings1 = tenant.settings
        assert tenant._settings is not None, "Settings should be loaded now"
        
        # Second access - should return cached data
        settings2 = tenant.settings
        
        # Both should be the same object (cached)
        assert settings1 is settings2, "Settings should be cached"
        
        # Verify data matches
        assert settings1['language'] == 'en'
        assert settings1['timezone'] == 'America/New_York'
        assert settings1['blocked_authors'] == ['user1', 'user2']
    
    def test_tenant_without_azure_config_raises_error(self, create_tenant):
        """Verify that accessing Azure config for tenant without config raises error."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        create_tenant(api_key=api_key)  # No Azure config
        
        tenant = get_tenant_by_api_key(api_key)
        
        with pytest.raises(TenantNotFoundError):
            _ = tenant.azure_config


# ============================================================================
# Additional Unit Tests
# ============================================================================

@pytest.mark.unit
class TestTenantContextBasics:
    """Basic unit tests for tenant context functionality."""
    
    def test_get_tenant_by_invalid_api_key_returns_none(self):
        """Verify that invalid API Key returns None."""
        tenant = get_tenant_by_api_key('invalid_key')
        assert tenant is None
    
    def test_get_tenant_by_empty_api_key_returns_none(self):
        """Verify that empty API Key returns None."""
        tenant = get_tenant_by_api_key('')
        assert tenant is None
    
    def test_get_tenant_by_none_api_key_returns_none(self):
        """Verify that None API Key returns None."""
        tenant = get_tenant_by_api_key(None)
        assert tenant is None
    
    def test_get_current_tenant_without_setting_returns_none(self):
        """Verify that getting current tenant without setting returns None."""
        tenant = get_current_tenant()
        assert tenant is None
    
    def test_set_and_get_current_tenant(self, create_tenant):
        """Verify setting and getting current tenant."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        create_tenant(api_key=api_key, company_name='Test Company')
        
        tenant = get_tenant_by_api_key(api_key)
        set_current_tenant(tenant)
        
        current = get_current_tenant()
        assert current is not None
        assert current.id == tenant.id
        assert current.company_name == 'Test Company'
    
    def test_tenant_has_integration(self, create_tenant, sample_integration_config):
        """Verify has_integration method."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        create_tenant(api_key=api_key, integrations=sample_integration_config)
        
        tenant = get_tenant_by_api_key(api_key)
        
        assert tenant.has_integration('slack') is True
        assert tenant.has_integration('sheets') is True
        assert tenant.has_integration('email') is False
    
    def test_tenant_get_integration(self, create_tenant, sample_integration_config):
        """Verify get_integration method."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        create_tenant(api_key=api_key, integrations=sample_integration_config)
        
        tenant = get_tenant_by_api_key(api_key)
        
        slack_integration = tenant.get_integration('slack')
        assert slack_integration is not None
        assert slack_integration['enabled'] is True
        assert slack_integration['config']['token'] == 'xoxb-test-token'
        
        email_integration = tenant.get_integration('email')
        assert email_integration is None
    
    def test_tenant_repr(self, create_tenant):
        """Verify tenant string representation."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        tenant_id = create_tenant(
            api_key=api_key,
            subdomain='test-company',
            company_name='Test Company Inc.'
        )
        
        tenant = get_tenant_by_api_key(api_key)
        repr_str = repr(tenant)
        
        assert 'Tenant' in repr_str
        assert str(tenant_id) in repr_str
        assert 'Test Company Inc.' in repr_str
        assert 'test-company' in repr_str
