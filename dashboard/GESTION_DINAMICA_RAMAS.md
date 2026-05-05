# 🌿 Gestión Dinámica de Ramas

## 🎯 Objetivo

Permitir **agregar, configurar y eliminar ramas dinámicamente** sin necesidad de editar código, con capacidad de:
- ✅ Agregar nuevas ramas al sistema
- ✅ Configurar reglas de validación por rama
- ✅ Agregar/quitar ramas de auto-aprobación
- ✅ Eliminar ramas cuando ya no se necesiten

---

## 🆕 ¿Qué Cambió?

### Antes
```python
# Ramas hardcodeadas en el código
branches = ["develop", "develop-pr", "releaseproyecto/r6"]

# Para agregar una rama:
# 1. Editar código Python
# 2. Reiniciar servidor
# 3. Configurar reglas manualmente
```

### Ahora
```bash
# Agregar rama desde API
curl -X POST -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"hotfix/production","config":{"enabled":true}}' \
  http://localhost:5000/api/branches/managed

# ¡Listo! La rama está disponible inmediatamente
```

---

## 📡 API Endpoints

### 1. GET /api/branches

Obtiene la lista de todas las ramas gestionadas.

**Response:**
```json
{
  "ok": true,
  "branches": [
    "develop",
    "develop-pr",
    "releaseproyecto/r6",
    "hotfix/production",
    "feature/new-module"
  ]
}
```

**Ejemplo:**
```bash
curl http://localhost:5000/api/branches
```

---

### 2. GET /api/branches/managed

Obtiene información detallada de todas las ramas.

**Response:**
```json
{
  "ok": true,
  "branches": [
    {
      "name": "develop",
      "exists": true,
      "has_rules": true,
      "rules": {
        "release_pattern": "r?6[.\\-]1",
        "sprints": ["sp69", "sp70"],
        "enabled": true
      },
      "in_auto_approve": true,
      "auto_approve_enabled": true
    },
    {
      "name": "hotfix/production",
      "exists": true,
      "has_rules": true,
      "rules": {
        "enabled": true,
        "warning_message": "PR hacia hotfix/production"
      },
      "in_auto_approve": false,
      "auto_approve_enabled": true
    }
  ]
}
```

**Ejemplo:**
```bash
curl http://localhost:5000/api/branches/managed
```

---

### 3. POST /api/branches/managed

Agrega una nueva rama al sistema.

**Headers:**
```
X-API-Key: tu-api-key
Content-Type: application/json
```

**Request Body:**
```json
{
  "name": "hotfix/production",
  "config": {
    "enabled": true,
    "release_pattern": "hotfix-.*",
    "release_message": "Hotfix debe seguir patrón hotfix-*",
    "warning_message": "PR hacia hotfix/production - revisar con cuidado"
  }
}
```

**Response:**
```json
{
  "ok": true,
  "branch": "hotfix/production"
}
```

**Ejemplos:**

```bash
# Agregar rama simple (solo con configuración por defecto)
curl -X POST \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"feature/new-module"}' \
  http://localhost:5000/api/branches/managed

# Agregar rama con configuración completa
curl -X POST \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "hotfix/production",
    "config": {
      "enabled": true,
      "release_pattern": "hotfix-.*",
      "release_message": "Hotfix debe seguir patrón hotfix-*",
      "sprints": [],
      "warning_message": "⚠️ PR hacia PRODUCCIÓN - revisar con cuidado"
    }
  }' \
  http://localhost:5000/api/branches/managed

# Agregar rama para release específico
curl -X POST \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "releaseproyecto/r7",
    "config": {
      "enabled": true,
      "release_pattern": "r?7[.\\-]\\d+",
      "release_message": "PR hacia r7 sin release r7.x en rama fuente",
      "sprints": ["sp71", "sp72"]
    }
  }' \
  http://localhost:5000/api/branches/managed
```

---

### 4. GET /api/branches/managed/{branch_name}

Obtiene información detallada de una rama específica.

**Response:**
```json
{
  "ok": true,
  "branch": {
    "name": "hotfix/production",
    "exists": true,
    "has_rules": true,
    "rules": {
      "enabled": true,
      "release_pattern": "hotfix-.*",
      "warning_message": "PR hacia hotfix/production"
    },
    "in_auto_approve": false,
    "auto_approve_enabled": true
  }
}
```

**Ejemplo:**
```bash
curl http://localhost:5000/api/branches/managed/hotfix%2Fproduction
```

---

### 5. DELETE /api/branches/managed/{branch_name}

Elimina una rama del sistema.

**Headers:**
```
X-API-Key: tu-api-key
```

**Response:**
```json
{
  "ok": true
}
```

**Ejemplo:**
```bash
curl -X DELETE \
  -H "X-API-Key: $API_KEY" \
  http://localhost:5000/api/branches/managed/feature%2Fold-module
```

**Nota:** Al eliminar una rama:
- ✅ Se remueve de la lista de ramas gestionadas
- ✅ Se remueve de auto-aprobación (si estaba)
- ✅ Se eliminan sus reglas de validación
- ✅ Los PRs existentes hacia esa rama no se ven afectados

---

## 🔄 Flujo Completo de Uso

### Escenario 1: Agregar Nueva Rama para Sprint

```bash
# 1. Agregar la rama
curl -X POST \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "releaseproyecto/r7",
    "config": {
      "enabled": true,
      "release_pattern": "r?7[.\\-]\\d+",
      "release_message": "PR hacia r7 sin release r7.x",
      "sprints": ["sp71", "sp72"],
      "sprint_message": "PR hacia r7 sin sprint sp71 o sp72"
    }
  }' \
  http://localhost:5000/api/branches/managed

# 2. Agregar a auto-aprobación
curl -X POST \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": true,
    "branches": ["develop", "develop-pr", "releaseproyecto/r6", "releaseproyecto/r7"]
  }' \
  http://localhost:5000/api/config/auto-approve

# 3. Verificar
curl http://localhost:5000/api/branches/managed/releaseproyecto%2Fr7
```

---

### Escenario 2: Rama Temporal para Hotfix

```bash
# 1. Crear rama temporal
curl -X POST \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "hotfix/critical-bug-2026-05",
    "config": {
      "enabled": true,
      "warning_message": "⚠️ HOTFIX CRÍTICO - Revisar inmediatamente"
    }
  }' \
  http://localhost:5000/api/branches/managed

# 2. Usar la rama para PRs urgentes
# ... (trabajo en la rama)

# 3. Cuando termine el hotfix, eliminar la rama
curl -X DELETE \
  -H "X-API-Key: $API_KEY" \
  http://localhost:5000/api/branches/managed/hotfix%2Fcritical-bug-2026-05
```

---

### Escenario 3: Migrar de Release Antiguo a Nuevo

```bash
# 1. Agregar nueva rama de release
curl -X POST \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "releaseproyecto/r8",
    "config": {
      "enabled": true,
      "release_pattern": "r?8[.\\-]\\d+",
      "sprints": ["sp73", "sp74"]
    }
  }' \
  http://localhost:5000/api/branches/managed

# 2. Actualizar auto-aprobación (agregar r8, mantener r7 temporalmente)
curl -X POST \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": true,
    "branches": ["develop", "develop-pr", "releaseproyecto/r7", "releaseproyecto/r8"]
  }' \
  http://localhost:5000/api/config/auto-approve

# 3. Después de migración completa, remover r7
curl -X DELETE \
  -H "X-API-Key: $API_KEY" \
  http://localhost:5000/api/branches/managed/releaseproyecto%2Fr7

# 4. Actualizar auto-aprobación (quitar r7)
curl -X POST \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": true,
    "branches": ["develop", "develop-pr", "releaseproyecto/r8"]
  }' \
  http://localhost:5000/api/config/auto-approve
```

---

## 🎨 Integración con Dashboard (UI)

### Panel de Gestión de Ramas

```javascript
// Cargar ramas gestionadas
async function loadManagedBranches() {
  const response = await fetch('/api/branches/managed', {
    headers: { 'X-API-Key': API_KEY }
  });
  const data = await response.json();
  
  renderBranchesTable(data.branches);
}

// Agregar nueva rama
async function addNewBranch() {
  const branchName = document.getElementById('new-branch-name').value;
  const config = {
    enabled: true,
    warning_message: `PR hacia ${branchName}`
  };
  
  const response = await fetch('/api/branches/managed', {
    method: 'POST',
    headers: {
      'X-API-Key': API_KEY,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ name: branchName, config })
  });
  
  if (response.ok) {
    alert('Rama agregada exitosamente');
    loadManagedBranches();
  }
}

// Eliminar rama
async function deleteBranch(branchName) {
  if (!confirm(`¿Eliminar la rama "${branchName}"?`)) return;
  
  const response = await fetch(
    `/api/branches/managed/${encodeURIComponent(branchName)}`,
    {
      method: 'DELETE',
      headers: { 'X-API-Key': API_KEY }
    }
  );
  
  if (response.ok) {
    alert('Rama eliminada exitosamente');
    loadManagedBranches();
  }
}

// Toggle auto-aprobación para una rama
async function toggleAutoApprove(branchName) {
  const config = await fetch('/api/config/auto-approve').then(r => r.json());
  
  const branches = config.branches || [];
  const index = branches.indexOf(branchName);
  
  if (index > -1) {
    branches.splice(index, 1); // Quitar
  } else {
    branches.push(branchName); // Agregar
  }
  
  await fetch('/api/config/auto-approve', {
    method: 'POST',
    headers: {
      'X-API-Key': API_KEY,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ enabled: config.enabled, branches })
  });
  
  loadManagedBranches();
}
```

### UI Propuesta

```
┌──────────────────────────────────────────────────────────────┐
│ 🌿 Gestión de Ramas                                         │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│ [➕ Agregar Nueva Rama]                                     │
│                                                              │
│ ┌────────────────────────────────────────────────────────┐ │
│ │ Rama                  │ Reglas │ Auto-Aprobación │ ... │ │
│ ├────────────────────────────────────────────────────────┤ │
│ │ develop               │   ✅   │      ✅         │ ⚙️🗑️│ │
│ │ develop-pr            │   ✅   │      ✅         │ ⚙️🗑️│ │
│ │ releaseproyecto/r6    │   ✅   │      ✅         │ ⚙️🗑️│ │
│ │ hotfix/production     │   ✅   │      ❌         │ ⚙️🗑️│ │
│ │ feature/new-module    │   ✅   │      ❌         │ ⚙️🗑️│ │
│ └────────────────────────────────────────────────────────┘ │
│                                                              │
│ ⚙️ = Configurar reglas                                      │
│ 🗑️ = Eliminar rama                                          │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 📋 Configuración de Reglas por Rama

### Campos Disponibles

```json
{
  "enabled": true,                    // Activar/desactivar validaciones
  "release_pattern": "r?6[.\\-]\\d+", // Regex para validar release
  "release_message": "Mensaje...",    // Mensaje si falla release
  "sprints": ["sp69", "sp70"],        // Lista de sprints válidos
  "sprint_message": "Mensaje...",     // Mensaje si falla sprint
  "warning_message": "Mensaje..."     // Mensaje de advertencia
}
```

### Ejemplos de Configuración

#### Rama de Desarrollo
```json
{
  "name": "develop",
  "config": {
    "enabled": true,
    "release_pattern": "r?6[.\\-]1",
    "release_message": "PR hacia develop sin release r6.1",
    "sprints": ["sp69", "sp70"],
    "sprint_message": "PR hacia develop sin sprint activo"
  }
}
```

#### Rama de Hotfix
```json
{
  "name": "hotfix/production",
  "config": {
    "enabled": true,
    "release_pattern": "hotfix-.*",
    "release_message": "Hotfix debe seguir patrón hotfix-*",
    "warning_message": "⚠️ PR hacia PRODUCCIÓN - revisar con cuidado"
  }
}
```

#### Rama Flexible (sin validaciones estrictas)
```json
{
  "name": "experimental/features",
  "config": {
    "enabled": true,
    "warning_message": "Rama experimental - sin validaciones estrictas"
  }
}
```

---

## 🔒 Seguridad

### Validaciones Implementadas

✅ **Nombre de rama:**
- No puede estar vacío
- Máximo 200 caracteres
- Se valida antes de agregar

✅ **Duplicados:**
- No se pueden agregar ramas que ya existen
- Error claro si se intenta

✅ **Eliminación:**
- Requiere API Key
- Limpia todas las referencias (auto-aprobación, reglas)

✅ **Configuración:**
- Se valida estructura de config
- Valores por defecto seguros

---

## 📊 Casos de Uso Reales

### 1. Nuevo Sprint (cada 2 semanas)

```bash
# Actualizar sprints en develop
curl -X PUT \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "sprints": ["sp71", "sp72"],
    "sprint_message": "PR hacia develop sin sprint sp71 o sp72"
  }' \
  http://localhost:5000/api/rules/branch/develop
```

### 2. Nuevo Release (cada 3 meses)

```bash
# Agregar nueva rama de release
curl -X POST \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "releaseproyecto/r7",
    "config": {
      "enabled": true,
      "release_pattern": "r?7[.\\-]\\d+",
      "sprints": ["sp71", "sp72"]
    }
  }' \
  http://localhost:5000/api/branches/managed

# Agregar a auto-aprobación
# (ver ejemplo en Escenario 1)
```

### 3. Hotfix Urgente

```bash
# Crear rama temporal
curl -X POST \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "hotfix/urgent-$(date +%Y%m%d)",
    "config": {
      "enabled": true,
      "warning_message": "⚠️ HOTFIX URGENTE"
    }
  }' \
  http://localhost:5000/api/branches/managed
```

---

## ✅ Beneficios

✅ **Flexibilidad** - Agregar/quitar ramas sin editar código
✅ **Rapidez** - Cambios aplicados inmediatamente
✅ **Control** - Configurar reglas específicas por rama
✅ **Limpieza** - Eliminar ramas obsoletas fácilmente
✅ **Auto-aprobación** - Gestionar qué ramas se auto-aprueban
✅ **Auditoría** - Todos los cambios quedan registrados

---

## 🚀 Próximos Pasos

### Implementar UI (Próxima Iteración)

1. **Panel de Gestión de Ramas**
   - Tabla con todas las ramas
   - Botón "Agregar Nueva Rama"
   - Botones de acción por rama

2. **Modal de Nueva Rama**
   - Campo: Nombre de rama
   - Toggle: Habilitar validaciones
   - Campos opcionales: release_pattern, sprints, etc.
   - Toggle: Agregar a auto-aprobación

3. **Modal de Configuración de Rama**
   - Editar todos los campos de configuración
   - Vista previa de cómo afectará a PRs
   - Botón "Guardar Cambios"

4. **Confirmación de Eliminación**
   - Mostrar cuántos PRs activos hay hacia esa rama
   - Advertir si está en auto-aprobación
   - Confirmar eliminación

---

## 📝 Checklist de Implementación

- [x] Crear funciones en `state.py`
  - [x] `load_managed_branches()`
  - [x] `save_managed_branches()`
  - [x] `add_managed_branch()`
  - [x] `remove_managed_branch()`
  - [x] `get_branch_info()`
- [x] Crear endpoints en `app.py`
  - [x] GET `/api/branches`
  - [x] GET `/api/branches/managed`
  - [x] POST `/api/branches/managed`
  - [x] GET `/api/branches/managed/{name}`
  - [x] DELETE `/api/branches/managed/{name}`
- [x] Documentación completa
- [ ] Implementar UI en dashboard
- [ ] Agregar tests
- [ ] Actualizar documentación de Notion

---

## 🎉 ¡Listo para Usar!

El sistema de gestión dinámica de ramas está **completamente funcional** vía API.

**Pruébalo ahora:**

```bash
# Ver ramas actuales
curl http://localhost:5000/api/branches

# Agregar una nueva
curl -X POST \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"mi-nueva-rama"}' \
  http://localhost:5000/api/branches/managed

# Ver información detallada
curl http://localhost:5000/api/branches/managed
```

**¡Ahora tienes control total sobre las ramas del sistema!** 🚀
