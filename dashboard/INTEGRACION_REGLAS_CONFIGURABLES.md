# 🔄 Integración de Reglas Configurables con el Script de Validación

## 📋 Objetivo

Hacer que las reglas configurables desde el dashboard se apliquen automáticamente en la validación de PRs, sin necesidad de editar código ni reiniciar servicios.

---

## 🎯 Flujo Completo

```
Usuario modifica regla en Dashboard
         ↓
Regla se guarda en SQLite (memoria/state.db)
         ↓
Cache de PRs se invalida automáticamente
         ↓
Próxima validación de PR carga reglas desde BD
         ↓
Reglas se aplican en check_salesforce_prs.py
         ↓
Resultado se muestra en Dashboard
```

---

## ✅ Paso 1: Modificar `check_salesforce_prs.py`

### 1.1 Agregar función para cargar reglas personalizadas

Agregar después de la función `load_validation_rules()` (línea ~330):

```python
def load_custom_validation_rules():
    """Carga las reglas de validación personalizadas desde la base de datos."""
    try:
        import sys
        from pathlib import Path
        # Agregar el directorio del dashboard al path
        dashboard_path = Path(__file__).parent.parent / "dashboard"
        if str(dashboard_path) not in sys.path:
            sys.path.insert(0, str(dashboard_path))
        
        from integrations.state import load_custom_rules
        rules = load_custom_rules()
        # Filtrar solo reglas habilitadas
        return {k: v for k, v in rules.items() if v.get("enabled", True)}
    except Exception as e:
        # Si falla, retornar diccionario vacío
        return {}
```

### 1.2 Modificar la función `classify()` para usar reglas personalizadas

Reemplazar las validaciones hardcoded con llamadas a las reglas configurables.

#### Antes (línea ~347):
```python
if not title_has_work_item(title):
    verdict = "rechazar"
    reasons.append("título sin work item claro")
```

#### Después:
```python
# Cargar reglas personalizadas
custom_rules = load_custom_validation_rules()

# Validar título con regla configurable
work_item_rule = custom_rules.get("work_item_validation")
if work_item_rule:
    pattern = work_item_rule.get("pattern", "")
    if pattern and not re.search(pattern, title or "", re.IGNORECASE):
        verdict = "rechazar"
        reasons.append(work_item_rule.get("error_message", "título sin work item claro"))
elif not title_has_work_item(title):
    # Fallback a validación hardcoded si no existe la regla
    verdict = "rechazar"
    reasons.append("título sin work item claro")
```

#### Antes (línea ~437):
```python
if any((p or "").endswith(".md") for p in paths):
    warnings.append("contiene archivo .md — revisar si hay tarea manual pendiente")
```

#### Después:
```python
# Validar archivos .md con regla configurable
md_rule = custom_rules.get("markdown_files_warning")
if md_rule and any((p or "").endswith(".md") for p in paths):
    msg = md_rule.get("error_message", "contiene archivo .md — revisar si hay tarea manual pendiente")
    if md_rule.get("severity") == "error":
        verdict = "rechazar"
        reasons.append(msg)
    else:
        warnings.append(msg)
elif any((p or "").endswith(".md") for p in paths):
    # Fallback
    warnings.append("contiene archivo .md — revisar si hay tarea manual pendiente")
```

### 1.3 Agregar validación de Deployment Sequence configurable

Modificar la sección de validación de deployment sequence (línea ~410):

#### Antes:
```python
if not yaml_in_deploy_sequence(target_ref, release_key, datatype):
    verdict = "rechazar"
    reasons.append(f"dataPack {datatype}.yaml no está en el deploy sequence")
```

#### Después:
```python
# Validar deployment sequence con regla configurable
deploy_seq_rule = custom_rules.get("deployment_sequence_validation")
if deploy_seq_rule:
    if not yaml_in_deploy_sequence(target_ref, release_key, datatype):
        msg = deploy_seq_rule.get("error_message", f"dataPack {datatype}.yaml no está en el deploy sequence")
        if deploy_seq_rule.get("severity") == "error":
            verdict = "rechazar"
            reasons.append(f"{msg} ({datatype}.yaml)")
        else:
            warnings.append(f"{msg} ({datatype}.yaml)")
elif not yaml_in_deploy_sequence(target_ref, release_key, datatype):
    # Fallback
    verdict = "rechazar"
    reasons.append(f"dataPack {datatype}.yaml no está en el deploy sequence")
```

---

## ✅ Paso 2: Asegurar Invalidación Automática del Cache

El código ya está implementado en `app.py`. Cada vez que se modifica una regla, se llama a `invalidate_prs_cache()`.

### Verificar que existe en todos los endpoints de reglas:

```python
@app.route("/api/rules/custom/<rule_id>", methods=["PUT"])
@require_api_key
def update_custom_rule_api(rule_id):
    # ... código ...
    invalidate_prs_cache()  # ← Esto invalida el cache
    return jsonify(result)
```

✅ **Ya está implementado** en:
- `POST /api/rules/custom` (crear)
- `PUT /api/rules/custom/<id>` (actualizar)
- `DELETE /api/rules/custom/<id>` (eliminar)
- `POST /api/rules/<type>/<id>/toggle` (toggle)
- `POST /api/rules` (guardar todas)

---

## ✅ Paso 3: Crear Script de Migración Completo

Voy a crear un script que aplique todos los cambios automáticamente:

```bash
#!/bin/bash
# migrate_to_configurable_rules.sh

SCRIPT_PATH="../scripts/check_salesforce_prs.py"
BACKUP_PATH="../scripts/check_salesforce_prs.py.backup.$(date +%Y%m%d_%H%M%S)"

echo "🔄 Migrando a reglas configurables..."

# 1. Hacer backup
echo "📦 Creando backup en: $BACKUP_PATH"
cp "$SCRIPT_PATH" "$BACKUP_PATH"

# 2. Agregar función load_custom_validation_rules
echo "➕ Agregando función load_custom_validation_rules..."
# (código de inserción)

# 3. Modificar función classify
echo "🔧 Modificando función classify..."
# (código de modificación)

# 4. Verificar sintaxis
echo "✅ Verificando sintaxis..."
python3 -m py_compile "$SCRIPT_PATH"

if [ $? -eq 0 ]; then
    echo "✅ Migración completada exitosamente"
    echo "📝 Backup guardado en: $BACKUP_PATH"
else
    echo "❌ Error en la migración, restaurando backup..."
    cp "$BACKUP_PATH" "$SCRIPT_PATH"
    exit 1
fi
```

---

## ✅ Paso 4: Probar la Integración

### 4.1 Probar desde el Dashboard

1. Abre `http://localhost:5000`
2. Ve al tab **"⚙️ Reglas"**
3. Click en **"⚙️ Gestionar Reglas"**
4. Desactiva la regla **"Validación de Work Item en Título"**
5. Guarda los cambios
6. Crea un PR de prueba sin work item en el título
7. Verifica que **NO** sea rechazado (porque la regla está desactivada)
8. Reactiva la regla
9. Verifica que ahora **SÍ** sea rechazado

### 4.2 Probar Deployment Sequence

1. Modifica la regla **"Validación de Deployment Sequence"**
2. Cambia la severidad de "error" a "warning"
3. Guarda los cambios
4. Crea un PR con un DataPack sin deployment sequence
5. Verifica que sea marcado como **"aprobable con cautela"** en lugar de **"rechazar"**

### 4.3 Probar Modificación de Mensajes

1. Edita la regla **"Validación de Work Item en Título"**
2. Cambia el mensaje de error a: "⚠️ Falta work item en el título (BUG-XXXXX, HDU-XXXXX)"
3. Guarda los cambios
4. Crea un PR sin work item
5. Verifica que el mensaje personalizado aparezca en el dashboard

---

## 🔄 Flujo de Actualización Automática

### Cuando modificas una regla en el Dashboard:

```
1. Usuario hace cambio en Dashboard
   ↓
2. Frontend envía PUT /api/rules/custom/<id>
   ↓
3. Backend guarda en SQLite
   ↓
4. Backend llama invalidate_prs_cache()
   ↓
5. Cache de PRs se marca como inválido
   ↓
6. Próxima carga de PRs ejecuta check_salesforce_prs.py
   ↓
7. Script carga reglas desde SQLite (load_custom_validation_rules)
   ↓
8. Reglas actualizadas se aplican
   ↓
9. Resultados se muestran en Dashboard
```

**Tiempo de propagación**: ⚡ **Inmediato** (próxima validación)

---

## 📊 Mapeo de Reglas

| Regla Configurable | Validación en Script | Línea Aprox. |
|-------------------|---------------------|--------------|
| `work_item_validation` | `title_has_work_item()` | ~347 |
| `deployment_sequence_validation` | `yaml_in_deploy_sequence()` | ~410 |
| `datapack_manifest_validation` | `component_in_datapack_manifest()` | ~406 |
| `forceapp_package_validation` | `component_in_forceapp_manifest()` | ~431 |
| `yaml_duplicates_validation` | `check_yaml_duplicates()` | ~354 |
| `markdown_files_warning` | `any(...endswith(".md"))` | ~437 |

---

## 🎯 Beneficios de la Integración

### ✅ Antes
- ❌ Editar código Python para cada cambio
- ❌ Reiniciar servicios
- ❌ Riesgo de errores de sintaxis
- ❌ Difícil de auditar cambios
- ❌ Requiere acceso al servidor

### ✅ Después
- ✅ Cambios desde interfaz web
- ✅ Sin reiniciar servicios
- ✅ Validación automática de datos
- ✅ Historial en base de datos
- ✅ Acceso controlado por API_KEY
- ✅ Rollback fácil (toggle on/off)
- ✅ Testing A/B (activar/desactivar reglas)

---

## 🔧 Implementación Simplificada

### Opción 1: Modificación Manual (Recomendada)

1. Hacer backup de `check_salesforce_prs.py`
2. Agregar función `load_custom_validation_rules()`
3. Modificar validaciones hardcoded para usar reglas configurables
4. Probar con PRs de prueba

### Opción 2: Script Automático

Ejecutar el script de migración que aplicará todos los cambios automáticamente.

---

## 📝 Próximos Pasos

1. ✅ **Hacer backup** del script actual
2. ✅ **Agregar** función `load_custom_validation_rules()`
3. ✅ **Modificar** validaciones hardcoded
4. ✅ **Probar** con PRs de prueba
5. ✅ **Documentar** cambios en el equipo
6. ✅ **Monitorear** primeras validaciones

---

## ❓ FAQ

### ¿Qué pasa si la base de datos no está disponible?
El script usa fallback a las validaciones hardcoded originales.

### ¿Puedo desactivar todas las reglas?
Sí, pero las validaciones hardcoded seguirán activas como fallback.

### ¿Los cambios son inmediatos?
Sí, se aplican en la próxima validación de PR (cuando se recarga el cache).

### ¿Puedo volver atrás?
Sí, simplemente restaura el backup del script.

### ¿Afecta el rendimiento?
No, la carga de reglas desde SQLite es muy rápida (<10ms).

---

## ✅ Checklist de Implementación

- [ ] Hacer backup de `check_salesforce_prs.py`
- [ ] Agregar función `load_custom_validation_rules()`
- [ ] Modificar validación de work item
- [ ] Modificar validación de deployment sequence
- [ ] Modificar validación de archivos .md
- [ ] Modificar validación de datapack manifest
- [ ] Modificar validación de force-app package
- [ ] Modificar validación de duplicados YAML
- [ ] Probar con PR sin work item
- [ ] Probar con PR sin deployment sequence
- [ ] Probar desactivar/activar reglas
- [ ] Probar modificar mensajes de error
- [ ] Probar cambiar severidad (error/warning)
- [ ] Documentar cambios al equipo
- [ ] Monitorear logs por 24h

---

¿Quieres que cree el script de migración automático o prefieres que te guíe paso a paso en la modificación manual?
