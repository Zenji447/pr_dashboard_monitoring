# 🚀 Plan de Migración a SaaS Multi-Tenant

## 📍 Estado Actual

**Versión:** v4.0 (tag creado)  
**Rama estable:** `stable-work`  
**Rama de desarrollo:** `feature/saas-multi-tenant` ⭐ (actual)

### ✅ Features v4.0 (Producción)
- Gestión dinámica de ramas
- Sistema de reglas configurables
- Auto-aprobación configurable
- Historial de cambios y auditoría
- UI completa de administración
- Base de datos SQLite

---

## 🎯 Objetivo: SaaS Multi-Tenant

Convertir la aplicación actual en un SaaS donde múltiples clientes puedan:
- Tener su propia configuración de Azure DevOps
- Gestionar sus propias ramas y reglas
- Configurar integraciones (Slack, Sheets, etc.)
- Pagar por planes (Starter, Professional, Enterprise)

---

## 📋 Roadmap de Desarrollo

### **Sprint 1: Multi-Tenancy Básico** (2 semanas)

#### Semana 1: Base de Datos y Modelos
- [ ] Crear esquema de base de datos multi-tenant
- [ ] Tabla `tenants` (id, subdomain, company_name, api_key, plan, status)
- [ ] Tabla `tenant_azure_config` (org_url, project, repository, pat_token)
- [ ] Tabla `tenant_settings` (configuraciones generales)
- [ ] Migración de datos actuales al primer tenant

#### Semana 2: Middleware y Aislamiento
- [ ] Middleware de identificación de tenant (por API key o subdomain)
- [ ] Context manager para tenant actual
- [ ] Modificar todas las queries para filtrar por tenant_id
- [ ] Sistema de aislamiento de datos entre tenants

### **Sprint 2: Configuración Dinámica** (2 semanas)

#### Semana 1: Eliminar Hardcoded Values
- [ ] Migrar Azure DevOps config a base de datos
- [ ] Migrar Slack config a base de datos
- [ ] Migrar Google Sheets config a base de datos
- [ ] Hacer todas las integraciones opcionales

#### Semana 2: UI de Configuración
- [ ] Panel de configuración de Azure DevOps
- [ ] Panel de configuración de Slack
- [ ] Panel de configuración de Google Sheets
- [ ] Panel de configuración general

### **Sprint 3: Autenticación y Onboarding** (1 semana)

- [ ] Sistema de registro de nuevos tenants
- [ ] Login/logout con sesiones
- [ ] Wizard de onboarding (5 pasos)
- [ ] Generación automática de API keys
- [ ] Email de bienvenida

### **Sprint 4: Planes y Monetización** (1 semana)

- [ ] Tabla `plans` con límites
- [ ] Enforcement de límites por plan
- [ ] Integración con Stripe
- [ ] UI de selección de plan
- [ ] Upgrade/downgrade de planes

### **Sprint 5: Features Adicionales** (2 semanas)

- [ ] Sistema de webhooks personalizados
- [ ] Plantillas de mensajes configurables
- [ ] Roles y permisos por tenant
- [ ] Analytics y métricas por tenant
- [ ] Configuración de UI (logo, colores)

---

## 🔧 Valores Hardcodeados a Eliminar

### ❌ Críticos (Sprint 1-2)
```python
# integrations/azure.py
ORG_URL = "https://dev.azure.com/salesforce-mx"  # → tenant_azure_config.org_url
PROJECT = "SalesForce"                            # → tenant_azure_config.project
REPOSITORY = "SalesForce"                         # → tenant_azure_config.repository

# integrations/slack.py
SLACK_PR_CHANNEL = "C08DXXXXXQP"                 # → tenant_integrations.config
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")   # → tenant_integrations.config

# services/sheets_service.py
SPREADSHEET_ID = "1Hn8XXXXXXXXXX"                # → tenant_integrations.config
SHEET_NAME = "PRs"                                # → tenant_integrations.config

# integrations/state.py
default_blocked_authors = ["Glenda Paiva"]        # → tenant_settings.blocked_authors

# app.py
LOCAL_REPO = Path("/home/zen6/cc/SalesForce")    # → tenant_settings.local_repo_path
```

### ⚠️ Opcionales (Sprint 5)
```python
# check_salesforce_prs.py
# Lógica de clasificación específica → Hacer configurable

# services/deploy_service.py
# Lógica de deploy específica → Hacer pluggable
```

---

## 🗄️ Esquema de Base de Datos Multi-Tenant

### Tabla: `tenants`
```sql
CREATE TABLE tenants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subdomain TEXT UNIQUE NOT NULL,
    company_name TEXT NOT NULL,
    api_key TEXT UNIQUE NOT NULL,
    plan TEXT DEFAULT 'starter',
    status TEXT DEFAULT 'trial',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    trial_ends_at TIMESTAMP,
    stripe_customer_id TEXT
);
```

### Tabla: `tenant_azure_config`
```sql
CREATE TABLE tenant_azure_config (
    tenant_id INTEGER PRIMARY KEY,
    org_url TEXT NOT NULL,
    project TEXT NOT NULL,
    repository TEXT NOT NULL,
    pat_token TEXT NOT NULL,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);
```

### Tabla: `tenant_integrations`
```sql
CREATE TABLE tenant_integrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    integration_type TEXT NOT NULL,
    enabled BOOLEAN DEFAULT 0,
    config TEXT NOT NULL,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);
```

### Tabla: `tenant_settings`
```sql
CREATE TABLE tenant_settings (
    tenant_id INTEGER PRIMARY KEY,
    language TEXT DEFAULT 'es',
    timezone TEXT DEFAULT 'America/Mexico_City',
    logo_url TEXT,
    primary_color TEXT DEFAULT '#3b82f6',
    blocked_authors TEXT,
    blocked_branches TEXT,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);
```

### Tabla: `tenant_users`
```sql
CREATE TABLE tenant_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    email TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT DEFAULT 'viewer',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
    UNIQUE(tenant_id, email)
);
```

### Tabla: `plans`
```sql
CREATE TABLE plans (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    price_monthly INTEGER NOT NULL,
    max_projects INTEGER,
    max_prs_per_month INTEGER,
    max_users INTEGER,
    features TEXT NOT NULL
);
```

---

## 🔐 Sistema de Autenticación

### Identificación de Tenant

**Opción 1: Por API Key** (Recomendado para MVP)
```
X-API-Key: tenant_abc123_key456
```

**Opción 2: Por Subdomain** (Para futuro)
```
https://acme.prmanager.com
https://salesforce.prmanager.com
```

### Context Manager
```python
from contextvars import ContextVar

current_tenant = ContextVar('current_tenant', default=None)

def get_current_tenant():
    return current_tenant.get()

def set_current_tenant(tenant_id):
    current_tenant.set(tenant_id)
```

---

## 📊 Planes y Precios (Propuesta)

### Starter - $49/mes
- 1 proyecto Azure DevOps
- 50 PRs/mes
- Reglas básicas
- Email support
- 2 usuarios

### Professional - $149/mes ⭐
- 5 proyectos
- PRs ilimitados
- Reglas personalizadas
- Auto-aprobación
- Slack integration
- Priority support
- 10 usuarios

### Enterprise - $499/mes
- Proyectos ilimitados
- Multi-tenant
- SSO/SAML
- API access
- Webhooks
- Dedicated support
- SLA 99.9%
- Usuarios ilimitados

---

## 🚀 Próximos Pasos Inmediatos

1. ✅ **Crear esquema de base de datos multi-tenant**
2. ✅ **Migrar datos actuales al primer tenant**
3. ✅ **Implementar middleware de identificación**
4. ✅ **Modificar queries para filtrar por tenant**
5. ✅ **Crear UI de configuración de Azure DevOps**

---

## 📝 Notas Importantes

- **Rama estable:** `stable-work` con tag `v4.0` - NO TOCAR
- **Rama de desarrollo:** `feature/saas-multi-tenant` - Desarrollo activo
- **Base de datos:** Crear nueva estructura, mantener compatibilidad con v4.0
- **Testing:** Probar con múltiples tenants desde el inicio
- **Seguridad:** Encriptar tokens y credenciales sensibles

---

## 🎯 Métricas de Éxito

- [ ] 2+ tenants funcionando simultáneamente
- [ ] Aislamiento completo de datos entre tenants
- [ ] Configuración 100% dinámica (sin hardcoded values)
- [ ] Onboarding completo en < 5 minutos
- [ ] Sistema de pagos funcionando
- [ ] Landing page + documentación

---

**Fecha de inicio:** Mayo 5, 2026  
**Estimación:** 6-8 semanas para MVP completo  
**Objetivo:** Primeros 5 clientes beta en 2 meses
