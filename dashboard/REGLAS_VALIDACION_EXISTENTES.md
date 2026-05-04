# 📋 Reglas de Validación de PRs Existentes

## Resumen

El sistema tiene **múltiples validaciones** que se aplican automáticamente a los Pull Requests. Aquí está el listado completo:

---

## 🔴 Validaciones que RECHAZAN el PR

### 1. **Work Item en el Título**
- **Validación**: El título debe contener un work item válido
- **Patrón**: `BUG-12345`, `HDU-12345`, `HU-12345`, o simplemente `12345` (5+ dígitos)
- **Mensaje**: "título sin work item claro"
- **Severidad**: ❌ RECHAZAR

### 2. **Release Pattern (rama develop)**
- **Validación**: La rama fuente debe contener el patrón de release configurado
- **Patrón por defecto**: `r?6[.\-]1` (acepta: r6.1, r6-1, 6.1, 6-1)
- **Mensaje**: "PR hacia develop sin release r6.1 en rama fuente"
- **Severidad**: ❌ RECHAZAR
- **Configurable**: ✅ Sí (desde el dashboard)

### 3. **Sprint (rama develop)**
- **Validación**: La rama fuente debe contener el sprint configurado
- **Valor por defecto**: `sp70`
- **Mensaje**: "PR hacia develop sin sprint sp70 en rama fuente"
- **Severidad**: ❌ RECHAZAR
- **Configurable**: ✅ Sí (desde el dashboard)
- **Nota**: Ahora soporta múltiples sprints simultáneos (ej: `sp69, sp70`)

### 4. **Componentes Duplicados en YAMLs**
- **Validación**: No debe haber componentes duplicados en archivos YAML
- **Mensaje**: "componente duplicado en {archivo}: {componente} (líneas X, Y)"
- **Severidad**: ❌ RECHAZAR

### 5. **DataPack sin Manifest**
- **Validación**: Los archivos `_DataPack.json` deben estar en el manifest base
- **Ubicación**: `manifest-pipeline/{release}/manifest-datapack/{datatype}.yaml`
- **Mensaje**: "dataPack {folder} no encontrado en manifest base {release}"
- **Severidad**: ❌ RECHAZAR

### 6. **DataPack sin Deploy Sequence** ⭐
- **Validación**: El archivo YAML del datatype debe estar en el `deploymentsequence`
- **Función**: `yaml_in_deploy_sequence(target_ref, release_key, datatype)`
- **Mensaje**: "dataPack {datatype}.yaml no está en el deploy sequence"
- **Severidad**: ❌ RECHAZAR
- **Nota**: **Esta es la regla de deploymentsequence que preguntaste**

### 7. **Force-app sin Package Metadata**
- **Validación**: Archivos nuevos en `/force-app/` deben tener entrada en `package-metadata.xml`
- **Ubicaciones verificadas**:
  - En la rama origen
  - En el manifest del destino: `manifest-pipeline/{release}/manifest-forceapp/package-metadata.xml`
- **Mensaje**: "force-app nuevo sin package-metadata.xml en origen ni en manifest destino: {member}"
- **Severidad**: ❌ RECHAZAR

### 8. **Target Fuera del Flujo Principal**
- **Validación**: El target debe ser una rama conocida (develop, develop-pr, releaseproyecto/r6)
- **Mensaje**: "target {target} fuera del flujo principal"
- **Severidad**: 🔍 REVISAR (no rechaza, pero marca para revisión)

---

## ⚠️ Validaciones que ADVIERTEN (Warnings)

### 9. **Archivos Markdown (.md)**
- **Validación**: Si el PR contiene archivos `.md`
- **Mensaje**: "contiene archivo .md — revisar si hay tarea manual pendiente"
- **Severidad**: ⚠️ WARNING
- **Resultado**: Marca el PR como "aprobable con cautela"

### 10. **Target develop-pr**
- **Validación**: PRs hacia `develop-pr` son flexibles (rama de bugfix)
- **Mensaje**: "target develop-pr, rama bugfix flexible"
- **Severidad**: ⚠️ WARNING
- **Configurable**: ✅ Sí (desde el dashboard)

---

## 📊 Resumen por Severidad

| Severidad | Cantidad | Reglas |
|-----------|----------|--------|
| ❌ RECHAZAR | 7 | Work item, Release pattern, Sprint, Duplicados YAML, DataPack sin manifest, **DataPack sin deploy sequence**, Force-app sin package |
| 🔍 REVISAR | 1 | Target fuera del flujo |
| ⚠️ WARNING | 2 | Archivos .md, Target develop-pr |

---

## 🔧 Reglas Configurables vs Hardcoded

### ✅ Configurables (desde el dashboard)

| Regla | Ubicación | Editable |
|-------|-----------|----------|
| Release Pattern | develop | ✅ |
| Sprint | develop | ✅ |
| Warning Message | develop-pr | ✅ |
| Enabled/Disabled | Todas las ramas | ✅ |

### 🔒 Hardcoded (en el código)

| Regla | Ubicación |
|-------|-----------|
| Work Item en título | `check_salesforce_prs.py` línea ~347 |
| Duplicados en YAML | `check_salesforce_prs.py` línea ~354 |
| DataPack sin manifest | `check_salesforce_prs.py` línea ~406 |
| **DataPack sin deploy sequence** | `check_salesforce_prs.py` línea ~410 |
| Force-app sin package | `check_salesforce_prs.py` línea ~431 |
| Archivos .md | `check_salesforce_prs.py` línea ~437 |

---

## 🎯 La Regla de DeploymentSequence

### ¿Qué hace?

Valida que cuando se agrega un archivo `_DataPack.json`, el archivo YAML correspondiente del datatype esté incluido en el archivo `deploymentsequence`.

### Código

```python
if not yaml_in_deploy_sequence(target_ref, release_key, datatype):
    verdict = "rechazar"
    reasons.append(f"dataPack {datatype}.yaml no está en el deploy sequence")
```

### Ejemplo

Si agregas:
- `/dataPack/VlocityCard/MyCard/MyCard_DataPack.json`

El sistema verifica que:
- `VlocityCard.yaml` esté en el `deploymentsequence` del release correspondiente

Si no está, **RECHAZA** el PR con el mensaje:
> "dataPack VlocityCard.yaml no está en el deploy sequence"

---

## 💡 ¿Quieres Convertir Reglas Hardcoded en Configurables?

Puedo crear reglas personalizadas en el módulo de Rules para:

1. **Work Item Validation**
   - Tipo: `branch_pattern` o `title_pattern`
   - Pattern: `\b(?:BUG|HDU|HU)?\s*-?\s*\d{5,}\b`

2. **Deployment Sequence Validation**
   - Tipo: `file_pattern` + `custom_validation`
   - Pattern: `.*_DataPack\.json$`
   - Validación: Verificar que el YAML esté en deploymentsequence

3. **Package Metadata Validation**
   - Tipo: `file_pattern` + `requires_manifest`
   - Pattern: `/force-app/.*`
   - Validación: Verificar entrada en package-metadata.xml

¿Quieres que convierta alguna de estas reglas hardcoded en reglas configurables desde el dashboard?

---

## 📝 Notas

- Las reglas configurables se guardan en SQLite (`memoria/state.db`)
- Las reglas hardcoded requieren editar `check_salesforce_prs.py`
- El sistema carga las reglas dinámicamente en cada validación
- Los cambios en reglas configurables no requieren reiniciar el servidor
