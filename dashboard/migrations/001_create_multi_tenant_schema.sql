-- ============================================================================
-- Migración 001: Esquema Multi-Tenant
-- Fecha: 2026-05-05
-- Descripción: Crea las tablas necesarias para soportar múltiples clientes
-- ============================================================================

-- Tabla principal de tenants (clientes)
CREATE TABLE IF NOT EXISTS tenants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subdomain TEXT UNIQUE NOT NULL,           -- ej: "salesforce", "acme"
    company_name TEXT NOT NULL,               -- ej: "Salesforce Mexico"
    api_key TEXT UNIQUE NOT NULL,             -- Key única para autenticación
    plan TEXT DEFAULT 'starter',              -- starter, professional, enterprise
    status TEXT DEFAULT 'trial',              -- trial, active, suspended, cancelled
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    trial_ends_at TIMESTAMP,
    stripe_customer_id TEXT,                  -- Para integración con Stripe
    notes TEXT                                -- Notas internas
);

-- Configuración de Azure DevOps por tenant
CREATE TABLE IF NOT EXISTS tenant_azure_config (
    tenant_id INTEGER PRIMARY KEY,
    org_url TEXT NOT NULL,                    -- ej: "https://dev.azure.com/salesforce-mx"
    project TEXT NOT NULL,                    -- ej: "SalesForce"
    repository TEXT NOT NULL,                 -- ej: "SalesForce"
    pat_token TEXT NOT NULL,                  -- Personal Access Token (encriptado)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);

-- Integraciones opcionales (Slack, Google Sheets, etc.)
CREATE TABLE IF NOT EXISTS tenant_integrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    integration_type TEXT NOT NULL,           -- slack, sheets, jira, webhook
    enabled BOOLEAN DEFAULT 0,
    config TEXT NOT NULL,                     -- JSON con configuración específica
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
    UNIQUE(tenant_id, integration_type)
);

-- Configuración general del tenant
CREATE TABLE IF NOT EXISTS tenant_settings (
    tenant_id INTEGER PRIMARY KEY,
    language TEXT DEFAULT 'es',               -- es, en
    timezone TEXT DEFAULT 'America/Mexico_City',
    logo_url TEXT,
    primary_color TEXT DEFAULT '#3b82f6',
    blocked_authors TEXT,                     -- JSON array
    blocked_branches TEXT,                    -- JSON array
    local_repo_path TEXT,                     -- Path al repo local (opcional)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);

-- Usuarios por tenant (para futuro sistema de login)
CREATE TABLE IF NOT EXISTS tenant_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    email TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    full_name TEXT,
    role TEXT DEFAULT 'viewer',               -- admin, reviewer, viewer
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
    UNIQUE(tenant_id, email)
);

-- Planes disponibles
CREATE TABLE IF NOT EXISTS plans (
    id TEXT PRIMARY KEY,                      -- starter, professional, enterprise
    name TEXT NOT NULL,
    price_monthly INTEGER NOT NULL,           -- En centavos (ej: 4900 = $49.00)
    max_projects INTEGER,                     -- NULL = ilimitado
    max_prs_per_month INTEGER,                -- NULL = ilimitado
    max_users INTEGER,                        -- NULL = ilimitado
    features TEXT NOT NULL,                   -- JSON array de features
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insertar planes por defecto
INSERT OR IGNORE INTO plans (id, name, price_monthly, max_projects, max_prs_per_month, max_users, features) VALUES
('starter', 'Starter', 4900, 1, 50, 2, '["basic_rules", "email_support"]'),
('professional', 'Professional', 14900, 5, NULL, 10, '["basic_rules", "custom_rules", "auto_approve", "slack", "priority_support"]'),
('enterprise', 'Enterprise', 49900, NULL, NULL, NULL, '["basic_rules", "custom_rules", "auto_approve", "slack", "sheets", "webhooks", "sso", "dedicated_support", "sla"]');

-- Índices para mejorar performance
CREATE INDEX IF NOT EXISTS idx_tenants_api_key ON tenants(api_key);
CREATE INDEX IF NOT EXISTS idx_tenants_subdomain ON tenants(subdomain);
CREATE INDEX IF NOT EXISTS idx_tenants_status ON tenants(status);
CREATE INDEX IF NOT EXISTS idx_tenant_users_email ON tenant_users(tenant_id, email);
CREATE INDEX IF NOT EXISTS idx_tenant_integrations_type ON tenant_integrations(tenant_id, integration_type);

-- ============================================================================
-- Notas de migración:
-- 
-- Esta migración crea la estructura base para multi-tenancy.
-- Los datos existentes en las tablas 'config' y 'kv' se migrarán
-- al primer tenant usando el script de migración Python.
-- ============================================================================
