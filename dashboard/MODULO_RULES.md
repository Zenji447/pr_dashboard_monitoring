# Módulo de Gestión de Reglas (Rules)

## 📋 Resumen

Se ha implementado un módulo completo de **Gestión de Reglas** en el dashboard que permite:

✅ **Ver** todas las reglas de validación (branch rules + custom rules)  
✅ **Modificar** reglas existentes  
✅ **Agregar** nuevas reglas personalizadas  
✅ **Eliminar** reglas personalizadas  
✅ **Activar/Desactivar** reglas con un toggle  

---

## 🎯 Características Principales

### 1. **Tab de Reglas en el Dashboard**
- Nuevo tab "⚙️ Reglas" en la navegación principal
- Vista dividida: Reglas de Branch | Reglas Personalizadas
- Tarjetas KPI mostrando estadísticas de reglas activas

### 2. **Reglas de Branch**
- Visualización de reglas por rama (develop, develop-pr, releaseproyecto/r6)
- Toggle para activar/desactivar cada regla
- Edición de patrones de release y sprints
- Configuración de mensajes de error personalizados

### 3. **Reglas Personalizadas**
- Crear reglas con validaciones custom
- Tipos de reglas:
  - **file_pattern**: Validar archivos por patrón
  - **branch_pattern**: Validar nombres de ramas
  - **content**: Validar contenido de archivos
- Severidades: Error, Warning, Info
- Tipos de validación:
  - exists: Archivo debe existir
  - not_exists: Archivo no debe existir
  - content: Validar contenido con regex
  - requires_test: Requiere archivo de test

### 4. **Modal de Gestión**
- Interfaz completa para editar reglas
- Tabs separados para Branch Rules y Custom Rules
- Formulario detallado para crear/editar reglas personalizadas
- Validación en tiempo real

---

## 🏗️ Arquitectura

### Backend

#### Nuevo Servicio: `services/rules_service.py`
```python
- get_all_rules()           # Obtiene todas las reglas
- get_branch_rules()        # Solo reglas de branch
- get_custom_rules()        # Solo reglas personalizadas
- update_branch_rule()      # Actualiza regla de branch
- create_custom_rule()      # Crea nueva regla custom
- update_custom_rule()      # Actualiza regla custom
- delete_custom_rule()      # Elimina regla custom
- toggle_rule()             # Activa/desactiva regla
```

#### Nuevos Endpoints en `app.py`

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/rules` | Obtiene todas las reglas |
| POST | `/api/rules` | Guarda todas las reglas |
| GET | `/api/rules/branch` | Obtiene reglas de branch |
| GET | `/api/rules/custom` | Obtiene reglas personalizadas |
| PUT | `/api/rules/branch/<branch_name>` | Actualiza regla de branch |
| POST | `/api/rules/custom` | Crea nueva regla custom |
| PUT | `/api/rules/custom/<rule_id>` | Actualiza regla custom |
| DELETE | `/api/rules/custom/<rule_id>` | Elimina regla custom |
| POST | `/api/rules/<type>/<id>/toggle` | Toggle regla |

### Frontend

#### Nuevo Panel: `panel-rules`
- Vista de resumen con KPIs
- Listado de reglas de branch
- Listado de reglas personalizadas
- Botones de acción (toggle, editar, eliminar)

#### Nuevos Modales
1. **Rules Management Modal**: Gestión completa de reglas
2. **Custom Rule Modal**: Crear/editar reglas personalizadas

#### Nuevas Funciones JavaScript
```javascript
- loadAllRules()              // Carga todas las reglas
- renderRulesPanel()          // Renderiza el panel principal
- renderRulesModal()          // Renderiza el modal de gestión
- toggleBranchRule()          // Toggle regla de branch
- toggleCustomRuleFromPanel() // Toggle regla custom
- openRulesModal()            // Abre modal de gestión
- saveCustomRule()            // Guarda regla personalizada
- saveAllRules()              // Guarda todos los cambios
- deleteCustomRuleFromModal() // Elimina regla custom
```

---

## 🎨 Interfaz de Usuario

### Panel Principal (Tab Rules)
```
┌─────────────────────────────────────────────────────┐
│ ⚙️ Reglas                                           │
├─────────────────────────────────────────────────────┤
│ [↻ Recargar Reglas] [⚙️ Gestionar Reglas]          │
├─────────────────────────────────────────────────────┤
│ 🌿 Reglas de Branch: 3    🔧 Reglas Personalizadas: 3│
│    2 activas                  2 activas              │
├──────────────────────┬──────────────────────────────┤
│ 🌿 Reglas de Branch  │ 🔧 Reglas Personalizadas     │
│                      │                              │
│ ┌──────────────────┐ │ ┌──────────────────────────┐ │
│ │ develop          │ │ │ manifest_validation      │ │
│ │ ✅ Activa        │ │ │ Validación de Manifest   │ │
│ │ Release: r6.1    │ │ │ ERROR | file_pattern     │ │
│ │ [✓ Activa]       │ │ │ [✓ Activa]               │ │
│ └──────────────────┘ │ └──────────────────────────┘ │
└──────────────────────┴──────────────────────────────┘
```

### Modal de Gestión
```
┌─────────────────────────────────────────────────────┐
│ ⚙️ Gestión de Reglas                        [X]     │
├─────────────────────────────────────────────────────┤
│ [🌿 Reglas de Branch] [🔧 Reglas Personalizadas]   │
├─────────────────────────────────────────────────────┤
│                                                     │
│ [Contenido según tab seleccionado]                 │
│                                                     │
├─────────────────────────────────────────────────────┤
│                    [Cancelar] [Guardar Cambios]     │
└─────────────────────────────────────────────────────┘
```

---

## 📝 Ejemplo de Uso

### 1. Ver Reglas Actuales
1. Ir al tab "⚙️ Reglas"
2. Ver resumen de reglas activas
3. Revisar reglas de branch y personalizadas

### 2. Modificar Regla de Branch
1. Click en "⚙️ Gestionar Reglas"
2. Tab "🌿 Reglas de Branch"
3. Editar campos (release pattern, sprints)
4. Click "Guardar Cambios"

### 3. Crear Nueva Regla Personalizada
1. Click en "⚙️ Gestionar Reglas"
2. Tab "🔧 Reglas Personalizadas"
3. Click "➕ Nueva Regla"
4. Completar formulario:
   - ID: `my_custom_rule`
   - Nombre: `Mi Regla Custom`
   - Tipo: `file_pattern`
   - Patrón: `.*\.apex$`
   - Severidad: `warning`
5. Click "Guardar Regla"

### 4. Activar/Desactivar Regla
1. Desde el panel principal o modal
2. Click en el botón de toggle
3. La regla se activa/desactiva inmediatamente

### 5. Eliminar Regla Personalizada
1. En el modal de gestión
2. Tab "🔧 Reglas Personalizadas"
3. Click "🗑️ Eliminar" en la regla deseada
4. Confirmar eliminación

---

## 🔒 Seguridad

- Todos los endpoints de modificación requieren `API_KEY`
- Validación de datos en backend
- Sanitización de inputs en frontend
- Límites de longitud en campos de texto

---

## 🌐 Internacionalización

El módulo soporta español e inglés:
- Todas las etiquetas están traducidas
- Mensajes de error en ambos idiomas
- Toggle de idioma en el header

---

## 🚀 Próximos Pasos Sugeridos

1. **Validación en Tiempo Real**: Probar regex patterns antes de guardar
2. **Historial de Cambios**: Log de modificaciones a reglas
3. **Import/Export**: Exportar/importar configuración de reglas
4. **Templates**: Plantillas de reglas comunes
5. **Testing**: Probar reglas contra PRs existentes

---

## 📦 Archivos Modificados/Creados

### Nuevos
- `services/rules_service.py` - Servicio de gestión de reglas

### Modificados
- `app.py` - Nuevos endpoints y imports
- `templates/index.html` - Nuevo tab, panel, modales y funciones JS
- `integrations/state.py` - Ya existían las funciones de persistencia

---

## ✅ Testing

Para probar el módulo:

1. **Iniciar el servidor**:
   ```bash
   python3 app.py
   ```

2. **Acceder al dashboard**:
   ```
   http://localhost:5000
   ```

3. **Ir al tab "⚙️ Reglas"**

4. **Probar funcionalidades**:
   - Ver reglas existentes
   - Activar/desactivar reglas
   - Crear nueva regla personalizada
   - Editar regla existente
   - Eliminar regla personalizada

---

## 🎉 ¡Listo!

El módulo de Rules está completamente funcional y listo para usar. Ahora puedes gestionar todas tus reglas de validación desde una interfaz visual intuitiva.
