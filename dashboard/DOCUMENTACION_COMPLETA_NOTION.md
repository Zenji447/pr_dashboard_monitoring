# 📚 Sistema de Gestión de PRs - Salesforce
## Documentación Completa para Notion

---

# 📖 Tabla de Contenidos

1. [Visión General del Sistema](#visión-general)
2. [Arquitectura](#arquitectura)
3. [Módulos Principales](#módulos-principales)
4. [Sistema de Reglas Configurables](#sistema-de-reglas)
5. [API Reference](#api-reference)
6. [Guías de Uso](#guías-de-uso)
7. [Troubleshooting](#troubleshooting)
8. [FAQ](#faq)

---

# 🎯 Visión General del Sistema {#visión-general}

## ¿Qué es?

Sistema web para **monitoreo, validación y auto-aprobación** de Pull Requests en Azure DevOps con integración a Slack y Google Sheets.

## Características Principales

- ✅ **Dashboard Web Interactivo**
- ✅ **Validación Automática de PRs**
- ✅ **Sistema de Reglas Configurables**
- ✅ **Auto-aprobación Inteligente**
- ✅ **Integración con Slack**
- ✅ **Exportación a Google Sheets**
- ✅ **Gestión de Bloqueos (Freeze)**
- ✅ **Monitoreo de Deployments**

## Stack Tecnológico

| Componente | Tecnología |
|------------|------------|
| **Backend** | Python 3.12 + Flask |
| **Frontend** | HTML5 + JavaScript (Vanilla) |
| **Base de Datos** | SQLite |
| **Integración Azure** | Azure CLI + REST API |
| **Integración Slack** | Slack API |
| **Integración Sheets** | Google Sheets API |

---

# 🏗️ Arquitectura {#arquitectura}

## Diagrama de Componentes

```
┌─────────────────────────────────────────────────────────────┐
│                      USUARIO (Navegador)                     │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   DASHBOARD (Flask App)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Frontend   │  │   Backend    │  │   Services   │     │
│  │  (HTML/JS)   │◄─┤  (Flask)     │◄─┤  (Python)    │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└────────────────────────┬────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│   SQLite    │  │ Azure DevOps│  │    Slack    │
│  (state.db) │  │     API     │  │     API     │
└─────────────┘  └─────────────┘  └─────────────┘
         │               │               │
         └───────────────┴───────────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │  Google Sheets API  │
              └─────────────────────┘
```

## Flujo de Datos

### 1. Validación de PR
```
PR creado en Azure DevOps
         ↓
Dashboard detecta nuevo PR
         ↓
check_salesforce_prs.py ejecuta validaciones
         ↓
Carga reglas desde SQLite
         ↓
Aplica validaciones configurables
         ↓
Genera veredicto (aprobable/rechazar/revisar)
         ↓
Muestra resultado en Dashboard
         ↓
Notifica en Slack (si aplica)
```

### 2. Modificación de Reglas
```
Usuario modifica regla en Dashboard
         ↓
Frontend envía PUT /api/rules/custom/<id>
         ↓
Backend valida datos
         ↓
Guarda en SQLite (state.db)
         ↓
Invalida cache de PRs
         ↓
Próxima validación usa nueva regla
         ↓
Cambios visibles inmediatamente
```

---

# 🧩 Módulos Principales {#módulos-principales}

## 1. Dashboard (Frontend)

### Ubicación
`templates/index.html`

### Componentes

#### Header
- Logo y título
- Badge de Azure DevOps
- Toggle de idioma (ES/EN)
- Spinner de carga
- Estado del sistema

#### Sidebar
- **Auto-aprobación**: Configurar ramas para auto-aprobar
- **Autores Bloqueados**: Lista de autores en freeze
- **Ramas Bloqueadas**: Lista de ramas en freeze
- **Validaciones de PR**: Resumen de reglas activas
- **Crear Rama**: Botón para crear nuevas ramas

#### Main Content
- **KPI Cards**: Métricas en tiempo real
- **Tabs**: Activos, Hoy, Ayer, Por Rango, Historial, **Reglas**
- **Tabla de PRs**: Lista de PRs con acciones
- **Filtros**: Por rama, fecha, ordenamiento

#### Modales
- **Nueva Rama**: Crear rama desde el dashboard
- **Validación de Reglas**: Configurar reglas de branch
- **Gestión de Reglas**: CRUD completo de reglas personalizadas
- **Nueva Regla Personalizada**: Formulario detallado

### Funcionalidades JavaScript

```javascript
// Principales funciones
- loadActivos()              // Carga PRs activos
- loadStats()                // Carga KPIs
- loadAllRules()             // Carga reglas configurables
- switchTab(tab)             // Cambia entre tabs
- approve(prId)              // Aprueba un PR
- reject(prId, comment)      // Rechaza un PR
- complete(prId)             // Completa un PR
- toggleAutoApprove()        // Toggle auto-aprobación
- addBlockedAuthor(name)     // Agrega autor bloqueado
- createCustomRule(data)     // Crea regla personalizada
- updateCustomRule(id, data) // Actualiza regla
- deleteCustomRule(id)       // Elimina regla
- toggleRule(type, id)       // Activa/desactiva regla
```

---

## 2. Backend (Flask)

### Ubicación
`app.py`

### Endpoints Principales

#### PRs
```python
GET  /api/prs                    # PRs activos
GET  /api/prs/completed          # PRs completados hoy
GET  /api/prs/completed/yesterday # PRs de ayer
GET  /api/prs/completed/range    # PRs por rango de fechas
POST /api/pr/<id>/approve        # Aprobar PR
POST /api/pr/<id>/reject         # Rechazar PR
POST /api/pr/<id>/complete       # Completar PR
```

#### Configuración
```python
GET  /api/config/auto-approve         # Config auto-aprobación
POST /api/config/auto-approve         # Guardar config
GET  /api/config/blocked-authors      # Autores bloqueados
POST /api/config/blocked-authors      # Guardar autores
GET  /api/config/blocked-branches     # Ramas bloqueadas
POST /api/config/blocked-branches     # Guardar ramas
```

#### Reglas (NUEVO)
```python
GET    /api/rules                     # Todas las reglas
POST   /api/rules                     # Guardar todas
GET    /api/rules/branch              # Reglas de branch
GET    /api/rules/custom              # Reglas personalizadas
PUT    /api/rules/branch/<name>       # Actualizar regla branch
POST   /api/rules/custom              # Crear regla custom
PUT    /api/rules/custom/<id>         # Actualizar regla custom
DELETE /api/rules/custom/<id>         # Eliminar regla custom
POST   /api/rules/<type>/<id>/toggle  # Toggle regla
```

#### Utilidades
```python
GET  /health                    # Health check
GET  /api/stats                 # Estadísticas
POST /api/auth/login            # Login Azure
POST /api/branch/create         # Crear rama
POST /api/prs/export-sheets     # Exportar a Sheets
```

### Autenticación

Todos los endpoints de modificación requieren API Key:

```python
@require_api_key
def endpoint():
    # Header: X-API-Key: tu-api-key
    # O: Authorization: Bearer tu-api-key
    pass
```

---

## 3. Servicios

### pr_service.py
```python
# Gestión de PRs
get_prs()                    # Obtiene PRs activos
invalidate_prs_cache()       # Invalida cache
```

### deploy_service.py
```python
# Monitoreo de deployments
get_deploy_status(pr_id)     # Estado del deploy
poll_deploy_background()     # Polling en background
```

### sheets_service.py
```python
# Integración Google Sheets
append_pr(pr_data)           # Agregar PR a sheet
update_deploy(pr_id, status) # Actualizar deploy
export_range(prs, from, to)  # Exportar rango
```

### rules_service.py (NUEVO)
```python
# Gestión de reglas
get_all_rules()              # Todas las reglas
get_branch_rules()           # Reglas de branch
get_custom_rules()           # Reglas personalizadas
update_branch_rule()         # Actualizar branch
create_custom_rule()         # Crear custom
update_custom_rule()         # Actualizar custom
delete_custom_rule()         # Eliminar custom
toggle_rule()                # Toggle on/off
```

---

## 4. Integraciones

### Azure DevOps (`integrations/azure.py`)

```python
# Funciones principales
get_token()                  # Token de Azure CLI
check_token()                # Verificar token
list_completed_prs()         # PRs completados
get_pr_policy_status(id)     # Estado de policies
get_pr_approval_date(id)     # Fecha de aprobación
complete_pr(id)              # Completar PR
set_pr_vote(id, vote)        # Votar PR
add_pr_comment(id, text)     # Agregar comentario
```

### Slack (`integrations/slack.py`)

```python
# Funciones principales
slack_api(method, data)      # Llamada a Slack API
notify_pr_slack(id, action)  # Notificar acción
find_pr_thread(id)           # Buscar hilo del PR
wait_for_pr_thread(id)       # Esperar hilo
```

### Estado (`integrations/state.py`)

```python
# Gestión de estado en SQLite
load_state()                 # Cargar estado
save_state(state)            # Guardar estado
load_auto_approve_config()   # Config auto-aprobación
save_auto_approve_config()   # Guardar config
load_blocked_authors()       # Autores bloqueados
save_blocked_authors()       # Guardar autores
load_blocked_branches()      # Ramas bloqueadas
save_blocked_branches()      # Guardar ramas

# Reglas de validación (NUEVO)
load_pr_validation_rules()   # Reglas de branch
save_pr_validation_rules()   # Guardar reglas branch
load_custom_rules()          # Reglas personalizadas
save_custom_rules()          # Guardar reglas custom
get_all_validation_rules()   # Todas las reglas
save_all_validation_rules()  # Guardar todas
```

---

# ⚙️ Sistema de Reglas Configurables {#sistema-de-reglas}

## Concepto

Sistema que permite **configurar validaciones de PRs desde el dashboard** sin necesidad de editar código.

## Tipos de Reglas

### 1. Reglas de Branch

Configuran validaciones específicas por rama destino.

**Ramas soportadas:**
- `develop`
- `develop-pr`
- `releaseproyecto/r6`

**Campos configurables:**

#### develop
```json
{
  "release_pattern": "r?6[.\\-]1",
  "release_message": "PR hacia develop sin release r6.1",
  "sprints": ["sp69", "sp70"],
  "sprint_message": "PR hacia develop sin sprint activo",
  "enabled": true
}
```

#### develop-pr
```json
{
  "warning_message": "target develop-pr, rama bugfix flexible",
  "enabled": true
}
```

### 2. Reglas Personalizadas

Validaciones custom configurables desde el dashboard.

**Estructura:**
```json
{
  "id": "rule_id",
  "name": "Nombre de la Regla",
  "description": "Descripción detallada",
  "enabled": true,
  "type": "file_pattern",
  "pattern": ".*\\.json$",
  "validation_type": "exists",
  "validation_pattern": "",
  "error_message": "Mensaje de error",
  "severity": "error"
}
```

**Tipos de Regla:**
- `file_pattern`: Valida archivos por patrón
- `title_pattern`: Valida título del PR
- `branch_pattern`: Valida nombre de rama
- `content`: Valida contenido de archivos

**Tipos de Validación:**
- `exists`: Archivo debe existir
- `not_exists`: Archivo no debe existir
- `content`: Validar contenido con regex
- `requires_test`: Requiere test asociado
- `requires_manifest`: Requiere entrada en manifest
- `no_duplicates`: No permite duplicados
- `custom`: Validación personalizada

**Severidades:**
- `error`: Rechaza el PR
- `warning`: Marca como "aprobable con cautela"
- `info`: Solo informativo

## Reglas Predefinidas

### 1. Validación de Work Item en Título
```json
{
  "id": "work_item_validation",
  "name": "Validación de Work Item en Título",
  "pattern": "\\b(?:BUG|HDU|HU)?\\s*-?\\s*\\d{5,}\\b",
  "type": "title_pattern",
  "severity": "error",
  "enabled": true
}
```

### 2. Validación de Deployment Sequence ⭐
```json
{
  "id": "deployment_sequence_validation",
  "name": "Validación de Deployment Sequence",
  "pattern": ".*_DataPack\\.json$",
  "type": "file_pattern",
  "validation_type": "custom",
  "validation_pattern": "deploymentsequence",
  "severity": "error",
  "enabled": true
}
```

### 3. Validación de DataPack en Manifest
```json
{
  "id": "datapack_manifest_validation",
  "name": "Validación de DataPack en Manifest",
  "pattern": ".*_DataPack\\.json$",
  "validation_type": "requires_manifest",
  "severity": "error",
  "enabled": true
}
```

### 4. Validación de Package Metadata
```json
{
  "id": "forceapp_package_validation",
  "name": "Validación de Package Metadata en Force-app",
  "pattern": "^/force-app/.*",
  "validation_type": "requires_manifest",
  "severity": "error",
  "enabled": true
}
```

### 5. Validación de Duplicados en YAML
```json
{
  "id": "yaml_duplicates_validation",
  "name": "Validación de Duplicados en YAML",
  "pattern": ".*\\.yaml$",
  "validation_type": "no_duplicates",
  "severity": "error",
  "enabled": true
}
```

### 6. Advertencia de Archivos Markdown
```json
{
  "id": "markdown_files_warning",
  "name": "Advertencia de Archivos Markdown",
  "pattern": ".*\\.md$",
  "severity": "warning",
  "enabled": true
}
```

## Flujo de Validación

```
1. PR creado/actualizado
   ↓
2. Dashboard carga PRs
   ↓
3. check_salesforce_prs.py ejecuta
   ↓
4. load_custom_validation_rules() carga reglas desde SQLite
   ↓
5. Para cada regla habilitada:
   - Verifica si aplica al PR
   - Ejecuta validación según tipo
   - Agrega error/warning según severidad
   ↓
6. Genera veredicto final:
   - "rechazar" si hay errores
   - "aprobable con cautela" si hay warnings
   - "aprobable" si todo OK
   ↓
7. Muestra resultado en Dashboard
```

---


# 📡 API Reference {#api-reference}

## Autenticación

Todos los endpoints de modificación requieren API Key:

```bash
# Header
X-API-Key: tu-api-key-aqui

# O Bearer Token
Authorization: Bearer tu-api-key-aqui

# O Query Parameter
?api_key=tu-api-key-aqui
```

## Endpoints de Reglas

### GET /api/rules
Obtiene todas las reglas (branch + custom).

**Response:**
```json
{
  "ok": true,
  "rules": {
    "branch_rules": {
      "develop": { ... },
      "develop-pr": { ... }
    },
    "custom_rules": {
      "work_item_validation": { ... },
      "deployment_sequence_validation": { ... }
    }
  }
}
```

### POST /api/rules
Guarda todas las reglas.

**Request:**
```json
{
  "branch_rules": { ... },
  "custom_rules": { ... }
}
```

**Response:**
```json
{
  "ok": true,
  "rules": { ... }
}
```

### GET /api/rules/custom
Obtiene solo reglas personalizadas.

**Response:**
```json
{
  "ok": true,
  "rules": {
    "rule_id": {
      "name": "Nombre",
      "description": "Descripción",
      "enabled": true,
      "type": "file_pattern",
      "pattern": ".*\\.json$",
      "severity": "error"
    }
  }
}
```

### POST /api/rules/custom
Crea una nueva regla personalizada.

**Request:**
```json
{
  "id": "my_custom_rule",
  "name": "Mi Regla Custom",
  "description": "Descripción",
  "type": "file_pattern",
  "pattern": ".*\\.test\\.js$",
  "validation_type": "exists",
  "error_message": "Falta archivo de test",
  "severity": "warning",
  "enabled": true
}
```

**Response:**
```json
{
  "ok": true,
  "rule": { ... }
}
```

### PUT /api/rules/custom/<rule_id>
Actualiza una regla personalizada.

**Request:**
```json
{
  "name": "Nombre Actualizado",
  "severity": "error",
  "enabled": false
}
```

**Response:**
```json
{
  "ok": true,
  "rule": { ... }
}
```

### DELETE /api/rules/custom/<rule_id>
Elimina una regla personalizada.

**Response:**
```json
{
  "ok": true
}
```

### POST /api/rules/<type>/<rule_id>/toggle
Activa/desactiva una regla.

**Parameters:**
- `type`: "branch" o "custom"
- `rule_id`: ID de la regla

**Response:**
```json
{
  "ok": true,
  "enabled": false
}
```

## Endpoints de PRs

### GET /api/prs
Obtiene PRs activos.

**Response:**
```json
{
  "ok": true,
  "prs": [
    {
      "id": 12345,
      "title": "BUG-12345 Fix issue",
      "source": "feature/bug-12345",
      "target": "develop",
      "createdBy": "John Doe",
      "verdict": "aprobable",
      "reasons": [],
      "warnings": [],
      "myVote": "approved",
      "canComplete": true,
      "hasConflicts": false
    }
  ]
}
```

### POST /api/pr/<pr_id>/approve
Aprueba un PR.

**Response:**
```json
{
  "ok": true,
  "ta_notified": true
}
```

### POST /api/pr/<pr_id>/reject
Rechaza un PR.

**Request:**
```json
{
  "comment": "Razón del rechazo"
}
```

**Response:**
```json
{
  "ok": true
}
```

### POST /api/pr/<pr_id>/complete
Completa un PR.

**Response:**
```json
{
  "ok": true
}
```

## Códigos de Error

| Código | Descripción |
|--------|-------------|
| 200 | OK |
| 201 | Created |
| 400 | Bad Request |
| 401 | Unauthorized (API Key inválida) |
| 404 | Not Found |
| 409 | Conflict (recurso ya existe) |
| 500 | Internal Server Error |
| 503 | Service Unavailable |

---

# 📖 Guías de Uso {#guías-de-uso}

## Guía Rápida: Primeros Pasos

### 1. Iniciar el Dashboard

```bash
cd dashboard
python3 app.py
```

Abre: `http://localhost:5000`

### 2. Ver PRs Activos

1. Tab **"⚡ Activos"** (por defecto)
2. Verás lista de PRs con su veredicto
3. Colores:
   - 🟢 Verde: Aprobable
   - 🟡 Amarillo: Aprobable con cautela
   - 🔵 Azul: Revisar
   - 🔴 Rojo: Rechazar

### 3. Aprobar un PR

1. Busca el PR en la lista
2. Click en **"Aprobar"**
3. El sistema:
   - Aprueba el PR en Azure
   - Notifica en Slack
   - Solicita revisión TA (si aplica)

#### Optimización de Notificación a TA ⭐

El sistema ahora verifica inteligentemente si debe notificar al TA:

**Escenario 1: Usuario aprueba ANTES que el TA**
- ✅ Se envía notificación al TA: "TA por favor revisa este PR"
- El TA aún no ha revisado, necesita ser notificado

**Escenario 2: Usuario aprueba DESPUÉS que el TA**
- ❌ NO se envía notificación al TA
- El TA ya aprobó, no tiene sentido notificarlo nuevamente

**Cómo funciona:**
```python
# El sistema verifica TAs pendientes antes de notificar
pending_tas = get_pr_ta_reviewers(pr_id, token, only_pending=True)

if pending_tas:
    # Hay TAs que aún no han aprobado
    notify_ta_slack(pr_id, pending_tas)
else:
    # Todos los TAs ya aprobaron, no notificar
    pass
```

**Beneficios:**
- Reduce notificaciones innecesarias
- Evita spam al TA
- Mejora la experiencia del usuario
- Notificaciones más relevantes

### 4. Completar un PR

1. PR debe estar aprobado
2. Click en **"Completar"**
3. El sistema:
   - Completa el PR en Azure
   - Inicia monitoreo de deploy
   - Exporta a Google Sheets

## Guía: Gestionar Reglas

### Ver Reglas Actuales

1. Tab **"⚙️ Reglas"**
2. Verás:
   - Resumen con KPIs
   - Reglas de Branch (izquierda)
   - Reglas Personalizadas (derecha)
3. Cada regla muestra:
   - Nombre
   - Estado (✅ Activa / ❌ Inactiva)
   - Descripción
   - Severidad

### Modificar una Regla

1. Tab **"⚙️ Reglas"**
2. Click **"⚙️ Gestionar Reglas"**
3. Tab **"🔧 Reglas Personalizadas"**
4. Busca la regla
5. Click **"✏️ Editar"**
6. Modifica campos:
   - Nombre
   - Descripción
   - Patrón (regex)
   - Tipo de validación
   - Mensaje de error
   - Severidad
   - Estado (activa/inactiva)
7. Click **"Guardar Regla"**
8. ✅ Cambios aplicados inmediatamente

### Crear Nueva Regla

1. Tab **"⚙️ Reglas"**
2. Click **"⚙️ Gestionar Reglas"**
3. Tab **"🔧 Reglas Personalizadas"**
4. Click **"➕ Nueva Regla"**
5. Completa formulario:
   - **ID**: Identificador único (ej: `my_rule`)
   - **Nombre**: Nombre descriptivo
   - **Descripción**: Qué valida la regla
   - **Tipo**: file_pattern, title_pattern, etc.
   - **Patrón**: Regex para matching
   - **Tipo de Validación**: exists, content, etc.
   - **Mensaje de Error**: Qué mostrar si falla
   - **Severidad**: error, warning, info
   - **Habilitada**: ✅ Sí
6. Click **"Guardar Regla"**
7. ✅ Regla creada y activa

### Activar/Desactivar Regla

**Opción 1: Desde el Panel Principal**
1. Tab **"⚙️ Reglas"**
2. Busca la regla
3. Click en el botón de toggle
4. ✅ Cambio inmediato

**Opción 2: Desde el Modal**
1. Tab **"⚙️ Reglas"**
2. Click **"⚙️ Gestionar Reglas"**
3. Tab **"🔧 Reglas Personalizadas"**
4. Busca la regla
5. Click en el toggle de estado
6. ✅ Cambio inmediato

### Eliminar Regla

1. Tab **"⚙️ Reglas"**
2. Click **"⚙️ Gestionar Reglas"**
3. Tab **"🔧 Reglas Personalizadas"**
4. Busca la regla
5. Click **"🗑️ Eliminar"**
6. Confirma la eliminación
7. ✅ Regla eliminada

## Guía: Configurar Auto-aprobación

### Activar Auto-aprobación

1. Sidebar → **"Auto-aprobación"**
2. Toggle **"Activar"** → ON
3. Selecciona ramas:
   - Click en cada rama para activar
   - Ramas activas se marcan en verde
4. ✅ Auto-aprobación activa

### Cómo Funciona

Cuando un PR cumple:
- ✅ Target en rama configurada
- ✅ Veredicto "aprobable"
- ✅ Sin conflictos
- ✅ Autor no bloqueado
- ✅ Rama no bloqueada

El sistema automáticamente:
1. Aprueba el PR
2. Notifica en Slack
3. Solicita revisión TA
4. Marca como auto-aprobado

## Guía: Gestionar Bloqueos (Freeze)

### Bloquear Autor

1. Sidebar → **"Autores bloqueados"**
2. Escribe nombre del autor
3. Click **"+"**
4. ✅ Autor bloqueado

**Efecto:**
- PRs del autor se marcan como "bloqueado"
- No se auto-aprueban
- Aparecen en sección separada

### Bloquear Rama

1. Sidebar → **"Ramas bloqueadas"**
2. Escribe nombre de la rama
3. Click **"+"**
4. ✅ Rama bloqueada

**Efecto:**
- PRs hacia esa rama se marcan como "frozen"
- No se auto-aprueban
- Aparecen en sección separada

### Desbloquear

1. Busca el autor/rama en la lista
2. Click en **"×"**
3. ✅ Desbloqueado

## Guía: Exportar a Google Sheets

### Exportar Rango

1. Tab **"📋 Historial"**
2. Selecciona fechas:
   - **Desde**: Fecha inicio
   - **Hasta**: Fecha fin
3. Click **"🔍 Buscar"**
4. Verifica los PRs
5. Click **"📊 Exportar a Sheets"**
6. ✅ Datos exportados

### Qué se Exporta

- ID del PR
- Título
- Autor
- Rama origen → destino
- Fecha de creación
- Fecha de cierre
- Fecha de aprobación
- Estado de deploy
- Auto-aprobado (Sí/No)
- Policy status
- Conflictos

## Guía: Cambiar Sprint Activo

### Escenario
Acaba de salir el sprint 71 (sp71) y necesitas actualizar la validación.

### Pasos

1. Tab **"⚙️ Reglas"**
2. Click **"⚙️ Gestionar Reglas"**
3. Tab **"🌿 Reglas de Branch"**
4. Busca **"develop"**
5. Campo **"Sprints"**: Cambia de `sp69, sp70` a `sp71`
6. Opcionalmente actualiza **"Sprint Message"**
7. Click **"Guardar Cambios"**
8. ✅ Listo!

**Resultado:**
- Todos los PRs nuevos hacia `develop` requerirán `sp71` en el nombre de la rama
- PRs sin `sp71` serán rechazados
- Cambio aplicado inmediatamente

### Múltiples Sprints Simultáneos

Si necesitas soportar dos sprints a la vez:

Campo **"Sprints"**: `sp70, sp71`

**Resultado:**
- PRs con `sp70` O `sp71` serán aceptados
- PRs sin ninguno serán rechazados

---

# 🔧 Troubleshooting {#troubleshooting}

## Problemas Comunes

### 1. Los cambios en reglas no se aplican

**Síntomas:**
- Modificas una regla en el dashboard
- Los PRs siguen validándose con la regla anterior

**Causas posibles:**
- Cache no se invalidó
- Script de validación no carga reglas desde BD

**Soluciones:**

```bash
# 1. Verificar que el cache se invalida
tail -f logs/dashboard.log | grep "invalidate"

# 2. Verificar que las reglas se guardaron
curl -s http://localhost:5000/api/rules/custom | python3 -m json.tool

# 3. Forzar recarga de PRs
# En el dashboard: Click "↻ Actualizar"

# 4. Verificar que el script carga reglas
# Ver logs de check_salesforce_prs.py
```

### 2. Error "TOKEN_EXPIRED"

**Síntomas:**
- Dashboard muestra error "TOKEN_EXPIRED"
- No se pueden cargar PRs

**Causa:**
- Token de Azure CLI expiró

**Solución:**

```bash
# 1. Re-autenticar
az login --allow-no-subscriptions --tenant 46bb22b8-4c2c-40ff-8360-7b6334821279

# 2. Verificar token
az account get-access-token --resource 499b84ac-1321-427f-aa17-267ca6975798

# 3. Recargar dashboard
# Click "↻ Actualizar"
```

### 3. Regla no se aplica en validación

**Síntomas:**
- Regla está activa en el dashboard
- Pero no se aplica en la validación de PRs

**Causas posibles:**
- Patrón regex incorrecto
- Tipo de validación no implementado
- Script no integrado

**Soluciones:**

```bash
# 1. Verificar que la regla está habilitada
curl -s http://localhost:5000/api/rules/custom/<rule_id> | python3 -m json.tool

# 2. Probar el patrón regex
python3 -c "import re; print(re.search(r'PATRON', 'TEXTO_PRUEBA'))"

# 3. Verificar integración en check_salesforce_prs.py
grep -n "load_custom_validation_rules" ../scripts/check_salesforce_prs.py

# 4. Ver logs de validación
# Buscar mensajes de error en la salida del script
```

### 4. Error al crear regla

**Síntomas:**
- Click "Guardar Regla"
- Error: "ID de regla requerido" o "Regla ya existe"

**Causas:**
- ID vacío o duplicado
- Campos requeridos faltantes

**Soluciones:**

```bash
# 1. Verificar que el ID es único
curl -s http://localhost:5000/api/rules/custom | python3 -m json.tool | grep "id"

# 2. Usar ID descriptivo sin espacios
# Bueno: deployment_sequence_validation
# Malo: Deployment Sequence

# 3. Completar campos requeridos
# - ID
# - Nombre
# - Tipo
```

### 5. Dashboard no carga

**Síntomas:**
- Página en blanco
- Error 500

**Causas posibles:**
- Servidor no está corriendo
- Error en el código
- Puerto ocupado

**Soluciones:**

```bash
# 1. Verificar que el servidor está corriendo
ps aux | grep "python3 app.py"

# 2. Ver logs del servidor
tail -f logs/dashboard.log

# 3. Verificar puerto
lsof -ti:5000

# 4. Reiniciar servidor
pkill -f "python3 app.py"
python3 app.py

# 5. Verificar sintaxis
python3 -m py_compile app.py
```

### 6. Base de datos corrupta

**Síntomas:**
- Error al cargar/guardar reglas
- "database is locked"

**Soluciones:**

```bash
# 1. Verificar permisos
ls -la ../memoria/state.db
chmod 664 ../memoria/state.db

# 2. Verificar integridad
sqlite3 ../memoria/state.db "PRAGMA integrity_check;"

# 3. Backup y recrear (último recurso)
cp ../memoria/state.db ../memoria/state.db.backup
rm ../memoria/state.db
# El sistema recreará la BD automáticamente
```

---

# ❓ FAQ {#faq}

## General

### ¿Qué es el sistema de reglas configurables?

Sistema que permite modificar las validaciones de PRs desde el dashboard web, sin necesidad de editar código Python ni reiniciar servicios.

### ¿Los cambios son inmediatos?

Sí, los cambios se aplican en la próxima validación de PR (cuando se recarga el cache). No requiere reiniciar el servidor.

### ¿Puedo desactivar todas las reglas?

Sí, pero las validaciones hardcoded originales seguirán activas como fallback de seguridad.

### ¿Qué pasa si la base de datos no está disponible?

El script usa fallback a las validaciones hardcoded originales. El sistema sigue funcionando.

### ¿Puedo volver atrás si algo sale mal?

Sí, de varias formas:
1. Toggle off de la regla (desactivar)
2. Editar y revertir cambios
3. Eliminar la regla
4. Restaurar backup del script

## Reglas

### ¿Cuántas reglas puedo crear?

No hay límite técnico, pero se recomienda mantener un número manejable (10-20) para facilitar la gestión.

### ¿Puedo crear reglas que validen múltiples condiciones?

Actualmente cada regla valida una condición. Para múltiples condiciones, crea varias reglas.

### ¿Las reglas se aplican en orden específico?

No, todas las reglas habilitadas se evalúan. El veredicto final es el más restrictivo (rechazar > revisar > aprobable con cautela > aprobable).

### ¿Puedo compartir reglas entre proyectos?

Las reglas están en SQLite. Puedes exportar/importar la tabla `config` entre instancias.

### ¿Cómo pruebo una regla antes de activarla?

1. Crea la regla desactivada
2. Prueba el patrón regex externamente
3. Activa la regla
4. Monitorea los primeros PRs
5. Ajusta según necesidad

## Validaciones

### ¿Qué es el "deployment sequence"?

Archivo que define el orden de despliegue de componentes DataPack. La regla valida que los YAMLs estén incluidos en este archivo.

### ¿Por qué mi PR fue rechazado?

Revisa la sección "Razones" en el dashboard. Ahí se listan todas las validaciones que fallaron.

### ¿Puedo aprobar un PR rechazado?

Sí, manualmente. El sistema solo recomienda, la decisión final es tuya.

### ¿Qué significa "aprobable con cautela"?

El PR pasó las validaciones críticas pero tiene warnings que debes revisar antes de aprobar.

## Auto-aprobación

### ¿Cómo funciona la auto-aprobación?

Si un PR cumple todos los criterios (rama configurada, veredicto aprobable, sin conflictos, autor no bloqueado), el sistema lo aprueba automáticamente.

### ¿Puedo desactivar la auto-aprobación temporalmente?

Sí, toggle off en el sidebar. Los PRs seguirán validándose pero no se aprobarán automáticamente.

### ¿Se notifica cuando se auto-aprueba un PR?

Sí, se envía notificación a Slack y se marca en el dashboard como "auto-aprobado".

## Integración

### ¿Cómo se integra con Azure DevOps?

Usa Azure CLI para autenticación y Azure DevOps REST API para operaciones (aprobar, completar, comentar).

### ¿Necesito configurar algo en Slack?

Sí, necesitas un Bot Token y el ID del canal. Se configura en el archivo `.env`.

### ¿Funciona con otros sistemas además de Azure DevOps?

Actualmente solo Azure DevOps. La arquitectura permite extender a otros sistemas (GitHub, GitLab, etc.).

## Seguridad

### ¿Quién puede modificar reglas?

Solo usuarios con la API Key válida. Se configura en el archivo `.env`.

### ¿Se auditan los cambios en reglas?

Los cambios se guardan en SQLite con timestamp. Puedes consultar el historial en la base de datos.

### ¿Puedo tener diferentes permisos por usuario?

Actualmente hay una sola API Key. Para permisos granulares, necesitarías implementar un sistema de autenticación más robusto.

## Performance

### ¿Afecta el rendimiento cargar reglas desde la BD?

No, la carga desde SQLite es muy rápida (<10ms). El impacto es negligible.

### ¿Cuántos PRs puede manejar el sistema?

El sistema ha sido probado con cientos de PRs sin problemas. El cuello de botella suele ser la API de Azure DevOps.

### ¿Se puede escalar horizontalmente?

Sí, pero necesitarías migrar de SQLite a una base de datos centralizada (PostgreSQL, MySQL).

---

# 📊 Métricas y KPIs

## KPIs del Dashboard

### PRs Activos
Número de PRs abiertos actualmente.

### Completados Hoy
PRs completados en el día actual.

### Pendientes Aprobación
PRs que aún no han sido aprobados.

### Listos para Completar
PRs aprobados que pueden ser completados.

### Tiempo Promedio de Revisión
Tiempo promedio desde creación hasta cierre del PR.

### Con Conflictos
PRs que tienen conflictos de merge.

### Tasa de Auto-aprobación
Porcentaje de PRs que fueron auto-aprobados.

## Métricas de Reglas

### Total de Reglas
Suma de reglas de branch + reglas personalizadas.

### Reglas Activas
Reglas con `enabled: true`.

### Reglas por Severidad
- Error: Rechazan el PR
- Warning: Marcan como cautela
- Info: Solo informativas

---

# 🔐 Seguridad

## Mejores Prácticas

### 1. API Key
- Usa una API Key fuerte (32+ caracteres)
- No la compartas en repositorios públicos
- Rótala periódicamente
- Guárdala en `.env` (nunca en código)

### 2. Acceso al Dashboard
- Usa HTTPS en producción
- Implementa autenticación adicional si es necesario
- Restringe acceso por IP si es posible

### 3. Base de Datos
- Backup regular de `state.db`
- Permisos restrictivos (664)
- Monitorea cambios sospechosos

### 4. Logs
- Revisa logs regularmente
- Monitorea intentos de acceso no autorizado
- Alerta en cambios críticos

---

# 🚀 Roadmap

## Funcionalidades Futuras

### Corto Plazo
- [ ] Historial de cambios en reglas
- [ ] Exportar/importar reglas
- [ ] Templates de reglas comunes
- [ ] Validación de regex en tiempo real

### Mediano Plazo
- [ ] Sistema de permisos granular
- [ ] Notificaciones por email
- [ ] Dashboard de métricas avanzado
- [ ] API pública documentada

### Largo Plazo
- [ ] Soporte para GitHub/GitLab
- [ ] Machine Learning para sugerencias
- [ ] Integración con JIRA
- [ ] App móvil

---

# �� Soporte

## Comandos Útiles

```bash
# Ver reglas actuales
curl -s http://localhost:5000/api/rules | python3 -m json.tool

# Ver solo reglas personalizadas
curl -s http://localhost:5000/api/rules/custom | python3 -m json.tool

# Health check
curl -s http://localhost:5000/health

# Ver PRs activos
curl -s http://localhost:5000/api/prs | python3 -m json.tool

# Verificar sintaxis del script
python3 -m py_compile ../scripts/check_salesforce_prs.py

# Ver logs en tiempo real
tail -f logs/dashboard.log

# Backup de base de datos
cp ../memoria/state.db ../memoria/state.db.backup.$(date +%Y%m%d)

# Restaurar backup
cp ../scripts/check_salesforce_prs.py.backup.* ../scripts/check_salesforce_prs.py
```

## Archivos Importantes

```
dashboard/
├── app.py                          # Backend Flask
├── templates/index.html            # Frontend
├── services/
│   ├── pr_service.py              # Gestión de PRs
│   ├── deploy_service.py          # Monitoreo de deploys
│   ├── sheets_service.py          # Google Sheets
│   └── rules_service.py           # Gestión de reglas ⭐
├── integrations/
│   ├── azure.py                   # Azure DevOps API
│   ├── slack.py                   # Slack API
│   └── state.py                   # SQLite (reglas, config)
└── .env                           # Configuración

../scripts/
└── check_salesforce_prs.py        # Script de validación ⭐

../memoria/
└── state.db                       # Base de datos SQLite ⭐
```

---

# 🎓 Glosario

**PR**: Pull Request - Solicitud de merge de código

**Veredicto**: Resultado de la validación (aprobable, rechazar, revisar, etc.)

**Auto-aprobación**: Sistema que aprueba PRs automáticamente si cumplen criterios

**Freeze**: Bloqueo temporal de autores o ramas

**Deployment Sequence**: Orden de despliegue de componentes

**DataPack**: Componente de Vlocity/Salesforce

**Manifest**: Archivo que lista componentes a desplegar

**Policy**: Regla de Azure DevOps (build, reviewers, etc.)

**TA**: Technical Architect - Revisor técnico

**Work Item**: Ticket de trabajo (BUG, HDU, HU)

**Severidad**: Nivel de importancia de una validación (error, warning, info)

**Fallback**: Comportamiento alternativo si falla el principal

**Cache**: Almacenamiento temporal de datos para mejorar rendimiento

**Toggle**: Interruptor on/off

**CRUD**: Create, Read, Update, Delete

---

# ✅ Checklist de Implementación

## Setup Inicial
- [ ] Instalar dependencias Python
- [ ] Configurar `.env` con credenciales
- [ ] Configurar Azure CLI
- [ ] Configurar Slack Bot
- [ ] Configurar Google Sheets API
- [ ] Iniciar servidor

## Configuración de Reglas
- [ ] Revisar reglas predefinidas
- [ ] Activar/desactivar según necesidad
- [ ] Crear reglas personalizadas
- [ ] Probar con PRs de prueba
- [ ] Ajustar mensajes de error
- [ ] Documentar reglas al equipo

## Integración
- [ ] Verificar integración con Azure
- [ ] Verificar notificaciones Slack
- [ ] Verificar exportación a Sheets
- [ ] Probar auto-aprobación
- [ ] Probar bloqueos (freeze)

## Monitoreo
- [ ] Configurar logs
- [ ] Monitorear primeras validaciones
- [ ] Ajustar reglas según feedback
- [ ] Documentar casos especiales

---

# 📄 Licencia y Créditos

**Sistema desarrollado para:** Claro Colombia - Salesforce Team

**Tecnologías utilizadas:**
- Python 3.12
- Flask
- SQLite
- Azure DevOps API
- Slack API
- Google Sheets API

**Última actualización:** Mayo 2026

---

# 🎉 ¡Fin de la Documentación!

Para más información o soporte, contacta al equipo de desarrollo.

**Dashboard URL:** `http://localhost:5000`

**¡Gracias por usar el sistema!** 🚀

