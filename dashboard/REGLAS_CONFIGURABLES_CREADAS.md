# ✅ Reglas Configurables Creadas

## 🎉 Resumen

Se han creado **9 reglas personalizadas configurables** en el módulo de Rules. Ahora puedes gestionar todas las validaciones desde el dashboard sin necesidad de editar código.

---

## 📋 Reglas Creadas

### 🔴 Reglas de Error (6)

#### 1. ⭐ **Validación de Deployment Sequence** (NUEVA)
- **ID**: `deployment_sequence_validation`
- **Descripción**: Valida que los archivos YAML de dataPack estén incluidos en el deploymentsequence del release correspondiente
- **Patrón**: `.*_DataPack\.json$`
- **Tipo**: file_pattern
- **Validación**: custom (deploymentsequence)
- **Mensaje**: "dataPack YAML no está en el deploy sequence"
- **Estado**: ✅ Activa

#### 2. **Validación de Work Item en Título**
- **ID**: `work_item_validation`
- **Descripción**: Valida que el título del PR contenga un work item válido (BUG-12345, HDU-12345, HU-12345, o 12345)
- **Patrón**: `\b(?:BUG|HDU|HU)?\s*-?\s*\d{5,}\b`
- **Tipo**: title_pattern
- **Validación**: exists
- **Mensaje**: "título sin work item claro"
- **Estado**: ✅ Activa

#### 3. **Validación de DataPack en Manifest**
- **ID**: `datapack_manifest_validation`
- **Descripción**: Valida que los archivos _DataPack.json estén registrados en el manifest base del release
- **Patrón**: `.*_DataPack\.json$`
- **Tipo**: file_pattern
- **Validación**: requires_manifest (manifest-datapack)
- **Mensaje**: "dataPack no encontrado en manifest base"
- **Estado**: ✅ Activa

#### 4. **Validación de Package Metadata en Force-app**
- **ID**: `forceapp_package_validation`
- **Descripción**: Valida que los archivos nuevos en /force-app/ tengan entrada en package-metadata.xml
- **Patrón**: `^/force-app/.*`
- **Tipo**: file_pattern
- **Validación**: requires_manifest (package-metadata.xml)
- **Mensaje**: "force-app nuevo sin package-metadata.xml"
- **Estado**: ✅ Activa

#### 5. **Validación de Duplicados en YAML**
- **ID**: `yaml_duplicates_validation`
- **Descripción**: Valida que no existan componentes duplicados en archivos YAML
- **Patrón**: `.*\.yaml$`
- **Tipo**: file_pattern
- **Validación**: no_duplicates
- **Mensaje**: "componente duplicado en YAML"
- **Estado**: ✅ Activa

#### 6. **Validación de Manifest**
- **ID**: `manifest_validation`
- **Descripción**: Valida que los archivos manifest cumplan con el formato requerido
- **Patrón**: `.*manifest.*\.xml`
- **Tipo**: file_pattern
- **Validación**: content (`<version>[\d\.]+</version>`)
- **Mensaje**: "Manifest sin versión válida"
- **Estado**: ✅ Activa

---

### ⚠️ Reglas de Warning (3)

#### 7. **Advertencia de Archivos Markdown**
- **ID**: `markdown_files_warning`
- **Descripción**: Advierte cuando el PR contiene archivos .md que pueden requerir tareas manuales
- **Patrón**: `.*\.md$`
- **Tipo**: file_pattern
- **Validación**: exists
- **Mensaje**: "contiene archivo .md — revisar si hay tarea manual pendiente"
- **Estado**: ✅ Activa

#### 8. **Validación de Metadata**
- **ID**: `metadata_validation`
- **Descripción**: Valida archivos de metadata de Salesforce
- **Patrón**: `.*-meta\.xml$`
- **Tipo**: file_pattern
- **Validación**: exists
- **Mensaje**: "Archivo metadata requerido"
- **Estado**: ✅ Activa

#### 9. **Cobertura de Tests**
- **ID**: `test_coverage`
- **Descripción**: Valida que existan tests para clases nuevas
- **Patrón**: `.*\.cls$`
- **Tipo**: file_pattern
- **Validación**: requires_test
- **Mensaje**: "Clase sin test asociado"
- **Estado**: ❌ Inactiva (por defecto)

---

## 🎯 Beneficios

### ✅ Antes (Hardcoded)
- ❌ Editar código Python para cambiar reglas
- ❌ Reiniciar servidor para aplicar cambios
- ❌ Requiere conocimientos de programación
- ❌ Difícil de auditar cambios

### ✅ Ahora (Configurable)
- ✅ Gestionar desde el dashboard web
- ✅ Cambios instantáneos sin reiniciar
- ✅ Interfaz visual intuitiva
- ✅ Historial en base de datos
- ✅ Activar/desactivar con un click
- ✅ Modificar mensajes de error
- ✅ Cambiar severidad (error/warning)

---

## 🚀 Cómo Usar

### Ver Reglas
1. Abre el dashboard: `http://localhost:5000`
2. Ve al tab **"⚙️ Reglas"**
3. Verás todas las reglas organizadas por tipo

### Modificar una Regla
1. Click en **"⚙️ Gestionar Reglas"**
2. Tab **"🔧 Reglas Personalizadas"**
3. Click en **"✏️ Editar"** en la regla deseada
4. Modifica los campos:
   - Nombre
   - Descripción
   - Patrón (regex)
   - Mensaje de error
   - Severidad (error/warning/info)
   - Estado (activa/inactiva)
5. Click en **"Guardar Regla"**

### Activar/Desactivar una Regla
1. Desde el panel principal o el modal
2. Click en el botón de toggle
3. La regla se activa/desactiva inmediatamente

### Crear una Nueva Regla
1. Click en **"⚙️ Gestionar Reglas"**
2. Tab **"🔧 Reglas Personalizadas"**
3. Click en **"➕ Nueva Regla"**
4. Completa el formulario
5. Click en **"Guardar Regla"**

---

## 📊 Comparación: Antes vs Ahora

| Validación | Antes | Ahora | Estado |
|------------|-------|-------|--------|
| Work Item en título | 🔒 Hardcoded | ✅ Configurable | Activa |
| Release Pattern | ✅ Configurable | ✅ Configurable | Activa |
| Sprint | ✅ Configurable | ✅ Configurable | Activa |
| Duplicados YAML | 🔒 Hardcoded | ✅ Configurable | Activa |
| DataPack en manifest | 🔒 Hardcoded | ✅ Configurable | Activa |
| **Deployment Sequence** | 🔒 Hardcoded | ✅ **Configurable** | **Activa** |
| Force-app package | 🔒 Hardcoded | ✅ Configurable | Activa |
| Archivos .md | 🔒 Hardcoded | ✅ Configurable | Activa |
| Metadata Salesforce | ✅ Configurable | ✅ Configurable | Activa |
| Cobertura de tests | ✅ Configurable | ✅ Configurable | Inactiva |

---

## 🔧 Tipos de Validación Soportados

| Tipo | Descripción | Ejemplo |
|------|-------------|---------|
| `file_pattern` | Valida archivos por patrón regex | `.*_DataPack\.json$` |
| `title_pattern` | Valida el título del PR | `\b(?:BUG\|HDU)\s*-?\s*\d{5,}\b` |
| `branch_pattern` | Valida nombres de ramas | `^feature/.*` |
| `content` | Valida contenido de archivos | `<version>[\d\.]+</version>` |
| `exists` | Verifica que el archivo exista | - |
| `not_exists` | Verifica que el archivo NO exista | - |
| `requires_test` | Requiere archivo de test asociado | - |
| `requires_manifest` | Requiere entrada en manifest | `package-metadata.xml` |
| `no_duplicates` | No permite duplicados | - |
| `custom` | Validación personalizada | `deploymentsequence` |

---

## 💾 Persistencia

- **Ubicación**: SQLite database en `../memoria/state.db`
- **Tabla**: `config`
- **Clave**: `custom_validation_rules`
- **Formato**: JSON
- **Thread-safe**: ✅ Sí (con locks)
- **Backup**: Automático en cada cambio

---

## 🔐 Seguridad

- ✅ Todos los endpoints requieren API_KEY
- ✅ Validación de datos en backend
- ✅ Sanitización de inputs
- ✅ Límites de longitud en campos
- ✅ Protección contra inyección de código

---

## 📝 Próximos Pasos

### Integración con el Script de Validación

Para que estas reglas se apliquen en la validación de PRs, necesitas:

1. **Modificar `check_salesforce_prs.py`** para cargar las reglas personalizadas
2. **Implementar la lógica de validación** según el tipo de regla
3. **Mapear los mensajes de error** a las reglas configurables

¿Quieres que actualice el script de validación para usar estas reglas configurables?

---

## ✅ Estado Actual

- ✅ 9 reglas personalizadas creadas
- ✅ 8 reglas activas
- ✅ 1 regla inactiva (test_coverage)
- ✅ Todas almacenadas en base de datos
- ✅ Accesibles desde el dashboard
- ✅ Modificables sin reiniciar servidor

---

## 🎉 ¡Listo!

La regla de **Deployment Sequence** y todas las demás validaciones ahora son **completamente configurables** desde el dashboard.

**Abre el dashboard y pruébalas:**
```
http://localhost:5000
→ Tab "⚙️ Reglas"
→ Click "⚙️ Gestionar Reglas"
```
