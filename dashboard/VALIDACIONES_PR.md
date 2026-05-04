# Módulo de Validaciones de PR

## Descripción

Este módulo permite gestionar de forma dinámica las validaciones de Pull Requests sin necesidad de editar código. Puedes configurar sprints, releases y otras validaciones directamente desde el dashboard.

## Características

### 1. **Interfaz de Configuración**
- Accede a la sección "Validaciones de PR" en el sidebar del dashboard
- Visualiza un resumen de las reglas activas para cada rama destino
- Botón "Configurar Reglas" para abrir el editor completo

### 2. **Reglas Configurables por Rama**

#### **develop**
- **Release Pattern**: Expresión regular para validar el patrón de release (ej: `r?6[.\-]1`)
- **Release Message**: Mensaje de error cuando no cumple el patrón de release
- **Sprints**: Lista de sprints activos (ej: `sp69, sp70`) - soporta múltiples sprints simultáneos
- **Sprint Message**: Mensaje de error cuando no cumple con ninguno de los sprints activos
- **Enabled**: Activar/desactivar validación para esta rama

#### **develop-pr**
- **Warning Message**: Mensaje de advertencia para PRs hacia esta rama
- **Enabled**: Activar/desactivar validación para esta rama

#### **releaseproyecto/r6**
- **Enabled**: Activar/desactivar validación para esta rama
- Sin restricciones adicionales por defecto

### 3. **Actualización Automática**
- Los cambios se guardan en la base de datos SQLite
- El script `check_salesforce_prs.py` carga las reglas dinámicamente
- El cache de PRs se invalida automáticamente al guardar cambios
- No requiere reiniciar el servidor

## Uso

### Cambiar el Sprint Actual

1. Abre el dashboard
2. Ve a la sección "Validaciones de PR" en el sidebar
3. Haz clic en "⚙️ Configurar Reglas"
4. En la sección "develop", actualiza el campo "Sprint" (ej: de `sp70` a `sp71`)
5. Opcionalmente, actualiza el "Sprint Message"
6. Haz clic en "Guardar Reglas"

### Cambiar el Patrón de Release

1. Abre el modal de configuración
2. En la sección "develop", actualiza el campo "Release Pattern"
3. Actualiza el "Release Message" si es necesario
4. Guarda los cambios

### Deshabilitar Validaciones para una Rama

1. Abre el modal de configuración
2. Desmarca el checkbox "Habilitado" para la rama deseada
3. Guarda los cambios

## API Endpoints

### GET `/api/config/pr-validation-rules`
Obtiene las reglas de validación actuales.

**Respuesta:**
```json
{
  "ok": true,
  "rules": {
    "develop": {
      "release_pattern": "r?6[.\\-]1",
      "release_message": "PR hacia develop sin release r6.1 en rama fuente",
      "sprint": "sp70",
      "sprint_message": "PR hacia develop sin sprint sp70 en rama fuente",
      "enabled": true
    },
    "develop-pr": {
      "warning_message": "target develop-pr, rama bugfix flexible",
      "enabled": true
    },
    "releaseproyecto/r6": {
      "enabled": true
    }
  }
}
```

### POST `/api/config/pr-validation-rules`
Guarda las reglas de validación.

**Requiere:** API Key en header `X-API-Key`

**Body:**
```json
{
  "rules": {
    "develop": {
      "release_pattern": "r?6[.\\-]1",
      "release_message": "PR hacia develop sin release r6.1 en rama fuente",
      "sprint": "sp71",
      "sprint_message": "PR hacia develop sin sprint sp71 en rama fuente",
      "enabled": true
    }
  }
}
```

**Respuesta:**
```json
{
  "ok": true,
  "rules": { ... }
}
```

## Estructura de Archivos

```
dashboard/
├── integrations/
│   └── state.py                    # Funciones para cargar/guardar reglas
├── services/
│   └── pr_service.py              # Servicio que usa las reglas
├── templates/
│   └── index.html                 # Interfaz del dashboard
├── app.py                         # Endpoints de la API
└── ../scripts/
    └── check_salesforce_prs.py    # Script que valida PRs
```

## Flujo de Validación

1. **Usuario actualiza reglas** en el dashboard
2. **Reglas se guardan** en SQLite (`memoria/state.db`)
3. **Cache de PRs se invalida** automáticamente
4. **Próxima carga de PRs** ejecuta `check_salesforce_prs.py`
5. **Script carga reglas** desde la base de datos
6. **Validaciones se aplican** según las reglas configuradas
7. **Resultados se muestran** en el dashboard

## Valores por Defecto

Si no se pueden cargar las reglas desde la base de datos, se usan estos valores por defecto:

```python
{
    "develop": {
        "release_pattern": r"r?6[.\-]1",
        "release_message": "PR hacia develop sin release r6.1 en rama fuente",
        "sprint": "sp70",
        "sprint_message": "PR hacia develop sin sprint sp70 en rama fuente",
        "enabled": True
    },
    "develop-pr": {
        "warning_message": "target develop-pr, rama bugfix flexible",
        "enabled": True
    },
    "releaseproyecto/r6": {
        "enabled": True
    }
}
```

## Notas Técnicas

- Las reglas se almacenan en la tabla `config` de SQLite
- La clave de configuración es `pr_validation_rules`
- El formato es JSON serializado
- Thread-safe mediante locks en `state.py`
- Compatible con el sistema existente de auto-aprobación

## Ejemplo de Uso Común

**Escenario:** Acaba de salir el sprint 71 (sp71)

1. Abre el dashboard
2. Ve a "Validaciones de PR" → "Configurar Reglas"
3. Cambia "Sprint" de `sp70` a `sp71`
4. Guarda los cambios
5. ¡Listo! Todos los PRs nuevos hacia `develop` requerirán `sp71` en el nombre de la rama

No necesitas:
- Editar código
- Reiniciar el servidor
- Hacer deploy
- Acceder por SSH

Todo se gestiona desde la interfaz web del dashboard.
