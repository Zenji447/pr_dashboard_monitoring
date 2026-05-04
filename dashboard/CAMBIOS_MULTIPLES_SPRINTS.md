# Cambios: Soporte para Múltiples Sprints Simultáneos

## Resumen
Se ha modificado el sistema para permitir **múltiples sprints activos simultáneamente** (ej: sp69 y sp70) en lugar de un solo sprint.

## Cambios Realizados

### 1. Backend (`integrations/state.py`)
- ✅ Cambiado `"sprint": "sp70"` por `"sprints": ["sp69", "sp70"]`
- ✅ Agregada migración automática para convertir configuraciones antiguas
- ✅ El sistema ahora acepta una **lista de sprints** en lugar de un string único

### 2. Frontend (`templates/index.html`)
- ✅ Campo de entrada actualizado para aceptar múltiples sprints separados por comas
- ✅ Placeholder actualizado: `"sp69, sp70"`
- ✅ Agregada ayuda visual: "Separar múltiples sprints con comas"
- ✅ Lógica de guardado actualizada para convertir el input en array
- ✅ Visualización actualizada para mostrar todos los sprints activos

### 3. Tests (`test_validation_api.py`)
- ✅ Actualizado para usar `"sprints": ["sp69", "sp70"]`
- ✅ Mensaje de resumen actualizado para mostrar múltiples sprints

### 4. Documentación (`VALIDACIONES_PR.md`)
- ✅ Actualizada para reflejar el nuevo campo `sprints` (plural)
- ✅ Ejemplos actualizados con múltiples sprints
- ✅ Instrucciones de uso actualizadas

## Cómo Usar

### Opción 1: Desde la Interfaz Web
1. Abre el dashboard
2. Ve a "Validaciones de PR" en el sidebar
3. Haz clic en "⚙️ Configurar Reglas"
4. En la sección "develop", ingresa los sprints separados por comas:
   ```
   sp69, sp70
   ```
5. Actualiza el mensaje si es necesario:
   ```
   PR hacia develop sin sprint sp69 o sp70 en rama fuente
   ```
6. Haz clic en "Guardar Reglas"

### Opción 2: Desde la API
```bash
curl -X POST http://localhost:5000/api/config/pr-validation-rules \
  -H "X-API-Key: tu-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "rules": {
      "develop": {
        "release_pattern": "r?6[.\\-]1",
        "release_message": "PR hacia develop sin release r6.1 en rama fuente",
        "sprints": ["sp69", "sp70"],
        "sprint_message": "PR hacia develop sin sprint sp69 o sp70 en rama fuente",
        "enabled": true
      }
    }
  }'
```

## Ejemplos de Configuración

### Un solo sprint
```json
{
  "sprints": ["sp70"]
}
```

### Dos sprints simultáneos
```json
{
  "sprints": ["sp69", "sp70"]
}
```

### Tres o más sprints
```json
{
  "sprints": ["sp68", "sp69", "sp70"]
}
```

## Migración Automática
El sistema incluye migración automática. Si tienes una configuración antigua con:
```json
{
  "sprint": "sp70"
}
```

Se convertirá automáticamente a:
```json
{
  "sprints": ["sp70"]
}
```

## Validación
La validación de PRs ahora acepta **cualquiera** de los sprints configurados en la lista. Por ejemplo, si configuras `["sp69", "sp70"]`, un PR con rama `feature/sp69-nueva-funcionalidad` o `feature/sp70-otra-funcionalidad` será válido.

## Notas Importantes
- ⚠️ **Importante**: El script de validación `check_salesforce_prs.py` (ubicado en `../scripts/`) también debe ser actualizado para leer `sprints` en lugar de `sprint`
- Los cambios son **retrocompatibles** gracias a la migración automática
- No es necesario reiniciar el servidor, los cambios se aplican inmediatamente
