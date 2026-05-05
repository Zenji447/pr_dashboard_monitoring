# 🎯 Próximos Pasos - Adaptación del Código

## 📍 Estado Actual

```
✅ Base de datos: Migrada a multi-tenant
✅ Tablas nuevas: Creadas y pobladas
✅ Servidor: Funcionando
✅ Dashboard: Operativo
❌ Código: Aún usa tablas viejas
```

---

## 🎯 Objetivo

Hacer que el código use las **tablas nuevas** en lugar de valores hardcodeados.

---

## 📋 Tareas Pendientes

### **Tarea 1: Crear Sistema de Identificación de Tenant** 🆕

**Archivo nuevo:** `integrations/tenant_context.py`

**¿Qué hace?**
- Identifica qué tenant está haciendo la petición (por API Key)
- Proporciona acceso a la configuración del tenant
- Funciona como un "contexto" global

**Ejemplo:**
```python
# Antes (hardcoded)
ORG_URL = "https://dev.azure.com/salesforce-mx"

# Después (dinámico)
tenant = get_current_tenant()
org_url = tenant.azure_config.org_url
```

---

### **Tarea 2: Modificar Azure DevOps** 🔧

**Archivo:** `integrations/azure.py`

**Cambios:**
```python
# ANTES (líneas 10-12)
ORG_URL = "https://dev.azure.com/salesforce-mx"
PROJECT = "SalesForce"
REPOSITORY = "SalesForce"

# DESPUÉS
def get_azure_config():
    tenant = get_current_tenant()
    return tenant.azure_config

ORG_URL = lambda: get_azure_config().org_url
PROJECT = lambda: get_azure_config().project
REPOSITORY = lambda: get_azure_config().repository
```

**Impacto:** Cada cliente podrá tener su propia configuración de Azure DevOps

---

### **Tarea 3: Modificar Slack** 🔧

**Archivo:** `integrations/slack.py`

**Cambios:**
```python
# ANTES
SLACK_PR_CHANNEL = "C08DXXXXXQP"
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")

# DESPUÉS
def get_slack_config():
    tenant = get_current_tenant()
    integration = tenant.get_integration('slack')
    if not integration or not integration.enabled:
        return None
    return integration.config

SLACK_PR_CHANNEL = lambda: get_slack_config()['channel']
SLACK_BOT_TOKEN = lambda: get_slack_config()['bot_token']
```

**Impacto:** Slack se vuelve opcional y configurable por cliente

---

### **Tarea 4: Modificar Google Sheets** 🔧

**Archivo:** `services/sheets_service.py`

**Cambios:**
```python
# ANTES
SPREADSHEET_ID = "1Hn8XXXXXXXXXX"
SHEET_NAME = "PRs"

# DESPUÉS
def get_sheets_config():
    tenant = get_current_tenant()
    integration = tenant.get_integration('sheets')
    if not integration or not integration.enabled:
        return None
    return integration.config

SPREADSHEET_ID = lambda: get_sheets_config()['spreadsheet_id']
SHEET_NAME = lambda: get_sheets_config()['sheet_name']
```

**Impacto:** Google Sheets se vuelve opcional y configurable por cliente

---

### **Tarea 5: Middleware de Autenticación** 🆕

**Archivo:** `app.py` (modificar)

**Agregar:**
```python
from integrations.tenant_context import set_current_tenant, get_tenant_by_api_key

@app.before_request
def identify_tenant():
    """Identifica el tenant antes de cada petición"""
    api_key = _request_api_key()
    if api_key:
        tenant = get_tenant_by_api_key(api_key)
        if tenant:
            set_current_tenant(tenant)
```

**Impacto:** Cada petición sabe a qué cliente pertenece

---

## 🎨 Comparación Visual

### **ANTES (Single-Tenant)**
```
Usuario → API Key → App → Valores Hardcoded
                           ├─ Azure: salesforce-mx
                           ├─ Slack: canal fijo
                           └─ Sheets: hoja fija
```

### **DESPUÉS (Multi-Tenant)**
```
Usuario → API Key → App → Identifica Tenant → Config del Tenant
                                               ├─ Azure: su config
                                               ├─ Slack: su canal
                                               └─ Sheets: su hoja
```

---

## ⏱️ Tiempo Estimado

| Tarea | Tiempo | Dificultad |
|-------|--------|------------|
| 1. Tenant Context | 30 min | Media |
| 2. Azure DevOps | 20 min | Fácil |
| 3. Slack | 20 min | Fácil |
| 4. Google Sheets | 20 min | Fácil |
| 5. Middleware | 15 min | Fácil |
| **Testing** | 30 min | - |
| **TOTAL** | ~2 horas | - |

---

## 🎯 Resultado Final

Después de estos cambios:

✅ **Tu app seguirá funcionando igual** (para ti)
✅ **Pero estará lista para múltiples clientes**
✅ **Cada cliente tendrá su propia configuración**
✅ **Las integraciones serán opcionales**

---

## 🚀 ¿Empezamos?

**Opción A:** Empezar ahora (te guío paso a paso)
**Opción B:** Hacer una pausa y continuar después
**Opción C:** Revisar primero el código actual

**¿Qué prefieres?**
