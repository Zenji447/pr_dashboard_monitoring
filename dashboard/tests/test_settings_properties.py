"""
Property-Based Tests for Tenant Settings

This module implements property-based tests for tenant settings management.

Correctness Properties Validated:
- Property 23: Default settings created with tenant
- Property 24: Settings update reflects on retrieval
- Property 25: Blocked authors/branches are valid JSON arrays
- Property 26: Language and timezone validation
"""
import secrets
import sqlite3
import json
from typing import Dict, Any, List
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
def language_strategy(draw):
    """Strategy for generating valid language codes."""
    return draw(st.sampled_from(['es', 'en', 'pt', 'fr', 'de']))


@st.composite
def timezone_strategy(draw):
    """Strategy for generating valid timezone identifiers."""
    timezones = [
        'America/Mexico_City',
        'America/New_York',
        'America/Los_Angeles',
        'America/Chicago',
        'America/Bogota',
        'America/Sao_Paulo',
        'Europe/London',
        'Europe/Paris',
        'Asia/Tokyo',
        'UTC'
    ]
    return draw(st.sampled_from(timezones))


@st.composite
def settings_data_strategy(draw):
    """Strategy for generating valid tenant settings."""
    return {
        'language': draw(language_strategy()),
        'timezone': draw(timezone_strategy()),
        'blocked_authors': draw(st.lists(st.text(min_size=1, max_size=50), min_size=0, max_size=10)),
        'blocked_branches': draw(st.lists(st.text(min_size=1, max_size=50), min_size=0, max_size=10)),
        'local_repo_path': draw(st.one_of(st.none(), st.text(min_size=1, max_size=100))),
        'logo_url': draw(st.one_of(st.none(), st.text(min_size=10, max_size=200).map(lambda x: f'https://example.com/{x}.png'))),
        'primary_color': draw(st.one_of(st.none(), st.text(min_size=7, max_size=7, alphabet='0123456789ABCDEF').map(lambda x: f'#{x}')))
    }


# ============================================================================
# Property 23: Default Settings Created with Tenant
# ============================================================================

@pytest.mark.property
class TestDefaultSettingsCreation:
    """
    Property 23: For any tenant T created without explicit settings,
    T.settings returns default values.
    """
    
    def test_tenant_without_settings_has_defaults(self, create_tenant):
        """Verify that tenants without explicit settings get defaults."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        
        # Create tenant without settings
        create_tenant(api_key=api_key)
        
        tenant = get_tenant_by_api_key(api_key)
        settings = tenant.settings
        
        # Verify default values
        assert settings is not None
        assert settings['language'] == 'es', "Default language should be 'es'"
        assert settings['timezone'] == 'America/Mexico_City', "Default timezone should be 'America/Mexico_City'"
        assert settings['blocked_authors'] == [], "Default blocked_authors should be empty list"
        assert settings['blocked_branches'] == [], "Default blocked_branches should be empty list"
        assert settings['local_repo_path'] is None, "Default local_repo_path should be None"
    
    @given(settings_data=settings_data_strategy())
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=50)
    def test_tenant_with_settings_stores_them(self, settings_data, create_tenant, cleanup_tenants):
        """Verify that explicit settings are stored correctly."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        
        # Create tenant with explicit settings
        create_tenant(api_key=api_key, settings=settings_data)
        
        tenant = get_tenant_by_api_key(api_key)
        retrieved_settings = tenant.settings
        
        # Verify all settings match
        assert retrieved_settings['language'] == settings_data['language']
        assert retrieved_settings['timezone'] == settings_data['timezone']
        assert retrieved_settings['blocked_authors'] == settings_data['blocked_authors']
        assert retrieved_settings['blocked_branches'] == settings_data['blocked_branches']
        assert retrieved_settings['local_repo_path'] == settings_data['local_repo_path']
        assert retrieved_settings['logo_url'] == settings_data['logo_url']
        assert retrieved_settings['primary_color'] == settings_data['primary_color']


# ============================================================================
# Property 24: Settings Update Reflects on Retrieval
# ============================================================================

@pytest.mark.property
class TestSettingsUpdate:
    """
    Property 24: For any tenant T with settings S1, after updating to S2,
    T.settings returns S2.
    """
    
    @given(
        initial_settings=settings_data_strategy(),
        new_language=language_strategy(),
        new_timezone=timezone_strategy()
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=30)
    def test_settings_update_reflects_on_retrieval(
        self, initial_settings, new_language, new_timezone, create_tenant, db_connection, cleanup_tenants
    ):
        """Verify that settings updates are reflected on retrieval."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        
        # Create tenant with initial settings
        tenant_id = create_tenant(api_key=api_key, settings=initial_settings)
        
        # Update language and timezone
        cursor = db_connection.cursor()
        cursor.execute("""
            UPDATE tenant_settings SET language = ?, timezone = ? 
            WHERE tenant_id = ?
        """, (new_language, new_timezone, tenant_id))
        db_connection.commit()
        clear_tenant_cache()
        
        # Verify updates
        tenant = get_tenant_by_api_key(api_key)
        settings = tenant.settings
        
        assert settings['language'] == new_language
        assert settings['timezone'] == new_timezone
    
    def test_update_blocked_authors(self, create_tenant, db_connection):
        """Verify updating blocked authors list."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        
        initial_settings = {
            'blocked_authors': ['user1', 'user2']
        }
        
        tenant_id = create_tenant(api_key=api_key, settings=initial_settings)
        
        # Update blocked authors
        new_blocked = ['user3', 'user4', 'user5']
        cursor = db_connection.cursor()
        cursor.execute("""
            UPDATE tenant_settings SET blocked_authors = ? 
            WHERE tenant_id = ?
        """, (json.dumps(new_blocked), tenant_id))
        db_connection.commit()
        clear_tenant_cache()
        
        # Verify update
        tenant = get_tenant_by_api_key(api_key)
        settings = tenant.settings
        
        assert settings['blocked_authors'] == new_blocked
    
    def test_update_blocked_branches(self, create_tenant, db_connection):
        """Verify updating blocked branches list."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        
        initial_settings = {
            'blocked_branches': ['temp/*', 'test/*']
        }
        
        tenant_id = create_tenant(api_key=api_key, settings=initial_settings)
        
        # Update blocked branches
        new_blocked = ['feature/*', 'hotfix/*']
        cursor = db_connection.cursor()
        cursor.execute("""
            UPDATE tenant_settings SET blocked_branches = ? 
            WHERE tenant_id = ?
        """, (json.dumps(new_blocked), tenant_id))
        db_connection.commit()
        clear_tenant_cache()
        
        # Verify update
        tenant = get_tenant_by_api_key(api_key)
        settings = tenant.settings
        
        assert settings['blocked_branches'] == new_blocked


# ============================================================================
# Property 25: Blocked Authors/Branches are Valid JSON Arrays
# ============================================================================

@pytest.mark.property
class TestBlockedListsValidJSON:
    """
    Property 25: For any tenant T, T.settings.blocked_authors and
    T.settings.blocked_branches must be valid JSON arrays.
    """
    
    @given(
        blocked_authors=st.lists(st.text(min_size=1, max_size=50), min_size=0, max_size=10),
        blocked_branches=st.lists(st.text(min_size=1, max_size=50), min_size=0, max_size=10)
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=50)
    def test_blocked_lists_are_valid_json_arrays(
        self, blocked_authors, blocked_branches, create_tenant, db_connection, cleanup_tenants
    ):
        """Verify that blocked lists are stored as valid JSON arrays."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        
        settings_data = {
            'blocked_authors': blocked_authors,
            'blocked_branches': blocked_branches
        }
        
        tenant_id = create_tenant(api_key=api_key, settings=settings_data)
        
        # Retrieve from database and verify JSON
        cursor = db_connection.cursor()
        cursor.execute("""
            SELECT blocked_authors, blocked_branches 
            FROM tenant_settings WHERE tenant_id = ?
        """, (tenant_id,))
        
        row = cursor.fetchone()
        assert row is not None
        
        # Should be able to parse as JSON
        stored_authors = json.loads(row[0])
        stored_branches = json.loads(row[1])
        
        assert isinstance(stored_authors, list)
        assert isinstance(stored_branches, list)
        assert stored_authors == blocked_authors
        assert stored_branches == blocked_branches
    
    def test_empty_blocked_lists_are_valid_json(self, create_tenant, db_connection):
        """Verify that empty blocked lists are stored as valid JSON."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        
        settings_data = {
            'blocked_authors': [],
            'blocked_branches': []
        }
        
        tenant_id = create_tenant(api_key=api_key, settings=settings_data)
        
        # Verify empty lists are stored as '[]'
        cursor = db_connection.cursor()
        cursor.execute("""
            SELECT blocked_authors, blocked_branches 
            FROM tenant_settings WHERE tenant_id = ?
        """, (tenant_id,))
        
        row = cursor.fetchone()
        
        authors = json.loads(row[0])
        branches = json.loads(row[1])
        
        assert authors == []
        assert branches == []


# ============================================================================
# Property 26: Language and Timezone Validation
# ============================================================================

@pytest.mark.property
class TestLanguageAndTimezoneValidation:
    """
    Property 26: For any tenant T, T.settings.language and T.settings.timezone
    must be valid values.
    """
    
    @given(
        language=language_strategy(),
        timezone=timezone_strategy()
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=50)
    def test_valid_language_and_timezone_accepted(
        self, language, timezone, create_tenant, cleanup_tenants
    ):
        """Verify that valid language and timezone values are accepted."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        
        settings_data = {
            'language': language,
            'timezone': timezone
        }
        
        create_tenant(api_key=api_key, settings=settings_data)
        
        tenant = get_tenant_by_api_key(api_key)
        settings = tenant.settings
        
        # Verify values are stored correctly
        assert settings['language'] == language
        assert settings['timezone'] == timezone
        
        # Verify language is a valid code
        assert language in ['es', 'en', 'pt', 'fr', 'de']
        
        # Verify timezone is a valid identifier
        assert '/' in timezone or timezone == 'UTC'
    
    def test_language_defaults_to_es(self, create_tenant, db_connection):
        """Verify that language defaults to 'es' if not specified."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        
        # Create tenant without settings
        tenant_id = create_tenant(api_key=api_key)
        
        tenant = get_tenant_by_api_key(api_key)
        settings = tenant.settings
        
        assert settings['language'] == 'es'
    
    def test_timezone_defaults_to_mexico_city(self, create_tenant):
        """Verify that timezone defaults to 'America/Mexico_City' if not specified."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        
        # Create tenant without settings
        create_tenant(api_key=api_key)
        
        tenant = get_tenant_by_api_key(api_key)
        settings = tenant.settings
        
        assert settings['timezone'] == 'America/Mexico_City'


# ============================================================================
# Additional Settings Tests
# ============================================================================

@pytest.mark.unit
class TestSettingsBasics:
    """Basic unit tests for tenant settings."""
    
    def test_settings_lazy_loading(self, create_tenant):
        """Verify that settings are lazy loaded."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        
        settings_data = {
            'language': 'en',
            'timezone': 'America/New_York'
        }
        
        create_tenant(api_key=api_key, settings=settings_data)
        
        tenant = get_tenant_by_api_key(api_key)
        
        # Before accessing, should not be loaded
        assert tenant._settings is None
        
        # After accessing, should be loaded
        settings = tenant.settings
        assert tenant._settings is not None
        assert settings == tenant._settings
    
    def test_update_logo_url(self, create_tenant, db_connection):
        """Verify updating logo URL."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        tenant_id = create_tenant(api_key=api_key)
        
        # Update logo URL
        new_logo = 'https://example.com/logo.png'
        cursor = db_connection.cursor()
        cursor.execute("""
            UPDATE tenant_settings SET logo_url = ? 
            WHERE tenant_id = ?
        """, (new_logo, tenant_id))
        db_connection.commit()
        clear_tenant_cache()
        
        # Verify update
        tenant = get_tenant_by_api_key(api_key)
        settings = tenant.settings
        
        assert settings['logo_url'] == new_logo
    
    def test_update_primary_color(self, create_tenant, db_connection):
        """Verify updating primary color."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        tenant_id = create_tenant(api_key=api_key)
        
        # Update primary color
        new_color = '#FF5733'
        cursor = db_connection.cursor()
        cursor.execute("""
            UPDATE tenant_settings SET primary_color = ? 
            WHERE tenant_id = ?
        """, (new_color, tenant_id))
        db_connection.commit()
        clear_tenant_cache()
        
        # Verify update
        tenant = get_tenant_by_api_key(api_key)
        settings = tenant.settings
        
        assert settings['primary_color'] == new_color
    
    def test_update_local_repo_path(self, create_tenant, db_connection):
        """Verify updating local repository path."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        tenant_id = create_tenant(api_key=api_key)
        
        # Update local repo path
        new_path = '/path/to/local/repo'
        cursor = db_connection.cursor()
        cursor.execute("""
            UPDATE tenant_settings SET local_repo_path = ? 
            WHERE tenant_id = ?
        """, (new_path, tenant_id))
        db_connection.commit()
        clear_tenant_cache()
        
        # Verify update
        tenant = get_tenant_by_api_key(api_key)
        settings = tenant.settings
        
        assert settings['local_repo_path'] == new_path
    
    def test_multiple_tenants_different_settings(self, create_tenant):
        """Verify that different tenants can have different settings."""
        # Tenant 1: Spanish, Mexico City
        api_key1 = f'prm_{secrets.token_urlsafe(32)}'
        create_tenant(api_key=api_key1, settings={
            'language': 'es',
            'timezone': 'America/Mexico_City'
        })
        
        # Tenant 2: English, New York
        api_key2 = f'prm_{secrets.token_urlsafe(32)}'
        create_tenant(api_key=api_key2, settings={
            'language': 'en',
            'timezone': 'America/New_York'
        })
        
        # Verify each tenant has their own settings
        tenant1 = get_tenant_by_api_key(api_key1)
        tenant2 = get_tenant_by_api_key(api_key2)
        
        assert tenant1.settings['language'] == 'es'
        assert tenant1.settings['timezone'] == 'America/Mexico_City'
        
        assert tenant2.settings['language'] == 'en'
        assert tenant2.settings['timezone'] == 'America/New_York'
    
    def test_settings_with_all_fields(self, create_tenant):
        """Verify creating settings with all fields."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        
        settings_data = {
            'language': 'en',
            'timezone': 'America/New_York',
            'blocked_authors': ['user1', 'user2'],
            'blocked_branches': ['temp/*', 'test/*'],
            'local_repo_path': '/path/to/repo',
            'logo_url': 'https://example.com/logo.png',
            'primary_color': '#FF5733'
        }
        
        create_tenant(api_key=api_key, settings=settings_data)
        
        tenant = get_tenant_by_api_key(api_key)
        settings = tenant.settings
        
        # Verify all fields
        assert settings['language'] == 'en'
        assert settings['timezone'] == 'America/New_York'
        assert settings['blocked_authors'] == ['user1', 'user2']
        assert settings['blocked_branches'] == ['temp/*', 'test/*']
        assert settings['local_repo_path'] == '/path/to/repo'
        assert settings['logo_url'] == 'https://example.com/logo.png'
        assert settings['primary_color'] == '#FF5733'
    
    def test_add_to_blocked_authors_list(self, create_tenant, db_connection):
        """Verify adding items to blocked authors list."""
        api_key = f'prm_{secrets.token_urlsafe(32)}'
        
        initial_settings = {
            'blocked_authors': ['user1']
        }
        
        tenant_id = create_tenant(api_key=api_key, settings=initial_settings)
        
        # Add more authors
        new_list = ['user1', 'user2', 'user3']
        cursor = db_connection.cursor()
        cursor.execute("""
            UPDATE tenant_settings SET blocked_authors = ? 
            WHERE tenant_id = ?
        """, (json.dumps(new_list), tenant_id))
        db_connection.commit()
        clear_tenant_cache()
        
        # Verify update
        tenant = get_tenant_by_api_key(api_key)
        settings = tenant.settings
        
        assert len(settings['blocked_authors']) == 3
        assert 'user2' in settings['blocked_authors']
        assert 'user3' in settings['blocked_authors']
