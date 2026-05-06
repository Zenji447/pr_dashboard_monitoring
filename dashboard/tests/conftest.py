"""
Pytest configuration and fixtures for testing
"""
import os
import sqlite3
import tempfile
import secrets
from pathlib import Path
from typing import Generator
import pytest

# Set test database path
TEST_DB_PATH = None


@pytest.fixture(scope="session")
def test_db_path() -> Generator[Path, None, None]:
    """Create a temporary database for testing."""
    global TEST_DB_PATH
    
    # Create temporary directory
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test_state.db"
    TEST_DB_PATH = db_path
    
    # Patch the database path in tenant_context module
    import integrations.tenant_context as tc
    original_db_path = tc._DB_PATH
    tc._DB_PATH = db_path
    
    # Create database schema
    _create_test_schema(db_path)
    
    yield db_path
    
    # Cleanup
    tc._DB_PATH = original_db_path
    if db_path.exists():
        db_path.unlink()
    os.rmdir(temp_dir)


def _create_test_schema(db_path: Path):
    """Create the multi-tenant database schema for testing."""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Create tenants table
    cursor.execute("""
        CREATE TABLE tenants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subdomain TEXT UNIQUE NOT NULL,
            company_name TEXT NOT NULL,
            api_key TEXT UNIQUE NOT NULL,
            plan TEXT NOT NULL CHECK(plan IN ('basic', 'pro', 'enterprise')),
            status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'inactive')),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    
    # Create tenant_azure_config table
    cursor.execute("""
        CREATE TABLE tenant_azure_config (
            tenant_id INTEGER PRIMARY KEY,
            org_url TEXT NOT NULL,
            project TEXT NOT NULL,
            repository TEXT NOT NULL,
            pat_token TEXT,
            FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
        )
    """)
    
    # Create tenant_integrations table
    cursor.execute("""
        CREATE TABLE tenant_integrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL,
            integration_type TEXT NOT NULL CHECK(integration_type IN ('slack', 'sheets', 'email', 'webhook')),
            enabled INTEGER NOT NULL DEFAULT 0,
            config TEXT NOT NULL DEFAULT '{}',
            FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
            UNIQUE(tenant_id, integration_type)
        )
    """)
    
    # Create tenant_settings table
    cursor.execute("""
        CREATE TABLE tenant_settings (
            tenant_id INTEGER PRIMARY KEY,
            language TEXT NOT NULL DEFAULT 'es',
            timezone TEXT NOT NULL DEFAULT 'America/Mexico_City',
            blocked_authors TEXT NOT NULL DEFAULT '[]',
            blocked_branches TEXT NOT NULL DEFAULT '[]',
            local_repo_path TEXT,
            logo_url TEXT,
            primary_color TEXT,
            FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
        )
    """)
    
    conn.commit()
    conn.close()


@pytest.fixture
def db_connection(test_db_path: Path) -> Generator[sqlite3.Connection, None, None]:
    """Provide a database connection for testing."""
    conn = sqlite3.connect(str(test_db_path))
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


@pytest.fixture(autouse=True)
def clear_tenant_cache(cleanup_tenants):
    """Clear tenant cache before and after each test."""
    from integrations.tenant_context import clear_tenant_cache
    clear_tenant_cache()
    yield
    clear_tenant_cache()


@pytest.fixture
def sample_tenant_data():
    """Provide sample tenant data for testing."""
    return {
        'subdomain': 'test-company',
        'company_name': 'Test Company Inc.',
        'api_key': f'prm_{secrets.token_urlsafe(32)}',
        'plan': 'enterprise',
        'status': 'active'
    }


@pytest.fixture
def sample_azure_config():
    """Provide sample Azure DevOps configuration."""
    return {
        'org_url': 'https://dev.azure.com/test-org',
        'project': 'TestProject',
        'repository': 'TestRepo',
        'pat_token': 'test_pat_token_12345'
    }


@pytest.fixture
def sample_integration_config():
    """Provide sample integration configuration."""
    return {
        'slack': {
            'enabled': True,
            'config': {
                'token': 'xoxb-test-token',
                'channel': '#test-channel'
            }
        },
        'sheets': {
            'enabled': True,
            'config': {
                'sheet_id': '1234567890abcdef',
                'credentials_path': '/path/to/creds.json'
            }
        }
    }


@pytest.fixture
def create_tenant(db_connection: sqlite3.Connection):
    """Factory fixture to create tenants in the test database."""
    def _create_tenant(
        subdomain: str = None,
        company_name: str = None,
        api_key: str = None,
        plan: str = 'basic',
        status: str = 'active',
        azure_config: dict = None,
        integrations: dict = None,
        settings: dict = None
    ) -> int:
        """
        Create a tenant in the test database.
        
        Returns:
            tenant_id: The ID of the created tenant
        """
        # Generate defaults
        if subdomain is None:
            subdomain = f'test-{secrets.token_hex(4)}'
        if company_name is None:
            company_name = f'Test Company {secrets.token_hex(2)}'
        if api_key is None:
            api_key = f'prm_{secrets.token_urlsafe(32)}'
        
        cursor = db_connection.cursor()
        
        # Insert tenant
        cursor.execute("""
            INSERT INTO tenants (subdomain, company_name, api_key, plan, status)
            VALUES (?, ?, ?, ?, ?)
        """, (subdomain, company_name, api_key, plan, status))
        
        tenant_id = cursor.lastrowid
        
        # Insert Azure config if provided
        if azure_config:
            cursor.execute("""
                INSERT INTO tenant_azure_config (tenant_id, org_url, project, repository, pat_token)
                VALUES (?, ?, ?, ?, ?)
            """, (
                tenant_id,
                azure_config.get('org_url', 'https://dev.azure.com/test'),
                azure_config.get('project', 'TestProject'),
                azure_config.get('repository', 'TestRepo'),
                azure_config.get('pat_token')
            ))
        
        # Insert integrations if provided
        if integrations:
            import json
            for integration_type, integration_data in integrations.items():
                cursor.execute("""
                    INSERT INTO tenant_integrations (tenant_id, integration_type, enabled, config)
                    VALUES (?, ?, ?, ?)
                """, (
                    tenant_id,
                    integration_type,
                    1 if integration_data.get('enabled') else 0,
                    json.dumps(integration_data.get('config', {}))
                ))
        
        # Insert settings if provided
        if settings:
            import json
            cursor.execute("""
                INSERT INTO tenant_settings (
                    tenant_id, language, timezone, blocked_authors, blocked_branches,
                    local_repo_path, logo_url, primary_color
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                tenant_id,
                settings.get('language', 'es'),
                settings.get('timezone', 'America/Mexico_City'),
                json.dumps(settings.get('blocked_authors', [])),
                json.dumps(settings.get('blocked_branches', [])),
                settings.get('local_repo_path'),
                settings.get('logo_url'),
                settings.get('primary_color')
            ))
        
        db_connection.commit()
        return tenant_id
    
    return _create_tenant


@pytest.fixture
def cleanup_tenants(db_connection: sqlite3.Connection):
    """Cleanup all tenants after test."""
    yield
    cursor = db_connection.cursor()
    cursor.execute("DELETE FROM tenant_settings")
    cursor.execute("DELETE FROM tenant_integrations")
    cursor.execute("DELETE FROM tenant_azure_config")
    cursor.execute("DELETE FROM tenants")
    db_connection.commit()
