# 📜 Sistema de Historial de Cambios en Reglas

## 🎯 Objetivo

Proporcionar **auditoría completa** de todos los cambios realizados en las reglas de validación, permitiendo:
- Ver quién cambió qué y cuándo
- Revertir cambios problemáticos
- Analizar patrones de modificación
- Cumplir con requisitos de auditoría

---

## 🗄️ Estructura de Datos

### Tabla: `rule_history`

```sql
CREATE TABLE rule_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id TEXT NOT NULL,              -- ID de la regla modificada
    rule_type TEXT NOT NULL,            -- 'branch' o 'custom'
    action TEXT NOT NULL,               -- 'create', 'update', 'delete', 'toggle'
    old_value TEXT,                     -- Valor anterior (JSON)
    new_value TEXT,                     -- Valor nuevo (JSON)
    changed_by TEXT,                    -- Usuario que hizo el cambio
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ip_address TEXT                     -- IP del usuario
);
```

### Ejemplo de Registro

```json
{
  "id": 1,
  "rule_id": "deployment_sequence_validation",
  "rule_type": "custom",
  "action": "update",
  "old_value": "{\"severity\":\"error\",\"enabled\":true}",
  "new_value": "{\"severity\":\"warning\",\"enabled\":true}",
  "changed_by": "juan.perez",
  "changed_at": "2026-05-04 15:30:45",
  "ip_address": "192.168.1.100"
}
```

---

## 📡 API Endpoints

### 1. GET /api/rules/history

Obtiene el historial de cambios en reglas.

**Query Parameters:**
- `rule_id` (opcional): Filtrar por ID de regla
- `rule_type` (opcional): Filtrar por tipo ('branch' o 'custom')
- `limit` (opcional): Número máximo de registros (default: 100)

**Headers:**
```
X-API-Key: tu-api-key
X-User-Name: nombre.usuario (opcional)
```

**Response:**
```json
{
  "ok": true,
  "history": [
    {
      "id": 5,
      "rule_id": "deployment_sequence_validation",
      "rule_type": "custom",
      "action": "toggle",
      "old_value": "{\"enabled\":true}",
      "new_value": "{\"enabled\":false}",
      "changed_by": "maria.garcia",
      "changed_at": "2026-05-04 16:45:00",
      "ip_address": "192.168.1.105"
    },
    {
      "id": 4,
      "rule_id": "work_item_validation",
      "rule_type": "custom",
      "action": "update",
      "old_value": "{\"severity\":\"error\"}",
      "new_value": "{\"severity\":\"warning\"}",
      "changed_by": "juan.perez",
      "changed_at": "2026-05-04 15:30:45",
      "ip_address": "192.168.1.100"
    }
  ]
}
```

**Ejemplos de Uso:**

```bash
# Ver todo el historial
curl -H "X-API-Key: $API_KEY" \
  http://localhost:5000/api/rules/history

# Ver historial de una regla específica
curl -H "X-API-Key: $API_KEY" \
  "http://localhost:5000/api/rules/history?rule_id=deployment_sequence_validation"

# Ver solo cambios en reglas personalizadas
curl -H "X-API-Key: $API_KEY" \
  "http://localhost:5000/api/rules/history?rule_type=custom"

# Ver últimos 20 cambios
curl -H "X-API-Key: $API_KEY" \
  "http://localhost:5000/api/rules/history?limit=20"
```

---

### 2. GET /api/rules/history/stats

Obtiene estadísticas del historial de cambios.

**Headers:**
```
X-API-Key: tu-api-key
```

**Response:**
```json
{
  "ok": true,
  "stats": {
    "total": 45,
    "by_action": {
      "create": 9,
      "update": 23,
      "delete": 2,
      "toggle": 11
    },
    "by_type": {
      "branch": 15,
      "custom": 30
    },
    "recent_24h": 7
  }
}
```

**Ejemplo de Uso:**

```bash
curl -H "X-API-Key: $API_KEY" \
  http://localhost:5000/api/rules/history/stats
```

---

### 3. POST /api/rules/history/{history_id}/rollback

Revierte un cambio en una regla.

**Headers:**
```
X-API-Key: tu-api-key
X-User-Name: nombre.usuario (opcional)
```

**Response:**
```json
{
  "ok": true,
  "change": {
    "id": 5,
    "rule_id": "deployment_sequence_validation",
    "rule_type": "custom",
    "action": "update",
    "old_value": "{\"severity\":\"error\"}",
    "new_value": "{\"severity\":\"warning\"}",
    "changed_by": "juan.perez",
    "changed_at": "2026-05-04 15:30:45"
  }
}
```

**Ejemplo de Uso:**

```bash
# Revertir el cambio con ID 5
curl -X POST \
  -H "X-API-Key: $API_KEY" \
  -H "X-User-Name: admin" \
  http://localhost:5000/api/rules/history/5/rollback
```

---

## 🔄 Flujo de Auditoría

### Cuando se Crea una Regla

```
1. Usuario crea regla "my_new_rule" desde el dashboard
   ↓
2. POST /api/rules/custom
   ↓
3. create_custom_rule() guarda la regla
   ↓
4. log_rule_change() registra:
   - rule_id: "my_new_rule"
   - action: "create"
   - old_value: null
   - new_value: "{...}"
   - changed_by: "usuario"
   ↓
5. Registro guardado en rule_history
```

### Cuando se Actualiza una Regla

```
1. Usuario modifica severidad de "error" a "warning"
   ↓
2. PUT /api/rules/custom/my_rule
   ↓
3. update_custom_rule() guarda el valor anterior
   ↓
4. log_rule_change() registra:
   - rule_id: "my_rule"
   - action: "update"
   - old_value: "{\"severity\":\"error\"}"
   - new_value: "{\"severity\":\"warning\"}"
   - changed_by: "usuario"
   ↓
5. Registro guardado en rule_history
```

### Cuando se Elimina una Regla

```
1. Usuario elimina regla "old_rule"
   ↓
2. DELETE /api/rules/custom/old_rule
   ↓
3. delete_custom_rule() guarda el valor antes de eliminar
   ↓
4. log_rule_change() registra:
   - rule_id: "old_rule"
   - action: "delete"
   - old_value: "{...}"
   - new_value: null
   - changed_by: "usuario"
   ↓
5. Registro guardado en rule_history
```

### Cuando se Activa/Desactiva una Regla

```
1. Usuario hace toggle de regla
   ↓
2. POST /api/rules/custom/my_rule/toggle
   ↓
3. toggle_rule() guarda estado anterior
   ↓
4. log_rule_change() registra:
   - rule_id: "my_rule"
   - action: "toggle"
   - old_value: "{\"enabled\":true}"
   - new_value: "{\"enabled\":false}"
   - changed_by: "usuario"
   ↓
5. Registro guardado en rule_history
```

---

## 🔙 Sistema de Rollback

### Cómo Funciona

El rollback revierte un cambio aplicando la operación inversa:

| Acción Original | Operación de Rollback |
|----------------|----------------------|
| **create** | Eliminar la regla |
| **delete** | Recrear la regla con old_value |
| **update** | Restaurar old_value |
| **toggle** | Restaurar old_value (estado anterior) |

### Ejemplo de Rollback

**Escenario:**
1. Usuario cambió severidad de "error" a "warning" (history_id: 5)
2. Esto causó que PRs problemáticos se aprobaran
3. Necesitamos revertir el cambio

**Solución:**
```bash
# Ver el cambio
curl -H "X-API-Key: $API_KEY" \
  "http://localhost:5000/api/rules/history?rule_id=my_rule&limit=1"

# Respuesta:
{
  "id": 5,
  "action": "update",
  "old_value": "{\"severity\":\"error\"}",
  "new_value": "{\"severity\":\"warning\"}"
}

# Revertir
curl -X POST \
  -H "X-API-Key: $API_KEY" \
  http://localhost:5000/api/rules/history/5/rollback

# Resultado: Severidad vuelve a "error"
```

---

## 📊 Casos de Uso

### 1. Auditoría de Seguridad

**Pregunta:** ¿Quién desactivó la regla de deployment sequence?

```bash
curl -H "X-API-Key: $API_KEY" \
  "http://localhost:5000/api/rules/history?rule_id=deployment_sequence_validation" \
  | jq '.history[] | select(.action=="toggle" and .new_value | contains("false"))'
```

**Respuesta:**
```json
{
  "id": 12,
  "changed_by": "juan.perez",
  "changed_at": "2026-05-04 14:30:00",
  "ip_address": "192.168.1.100"
}
```

---

### 2. Análisis de Cambios Frecuentes

**Pregunta:** ¿Qué reglas se modifican más?

```bash
curl -H "X-API-Key: $API_KEY" \
  http://localhost:5000/api/rules/history \
  | jq '[.history[] | .rule_id] | group_by(.) | map({rule: .[0], count: length}) | sort_by(.count) | reverse'
```

**Respuesta:**
```json
[
  {"rule": "deployment_sequence_validation", "count": 15},
  {"rule": "work_item_validation", "count": 8},
  {"rule": "develop", "count": 5}
]
```

---

### 3. Revertir Cambios Masivos

**Escenario:** Se hicieron varios cambios problemáticos en la última hora

```bash
# Ver cambios recientes
curl -H "X-API-Key: $API_KEY" \
  "http://localhost:5000/api/rules/history?limit=10"

# Revertir cada uno
for id in 15 14 13; do
  curl -X POST \
    -H "X-API-Key: $API_KEY" \
    "http://localhost:5000/api/rules/history/$id/rollback"
done
```

---

### 4. Reportes de Cumplimiento

**Generar reporte mensual:**

```bash
# Obtener todos los cambios
curl -H "X-API-Key: $API_KEY" \
  "http://localhost:5000/api/rules/history?limit=1000" \
  > rule_changes_$(date +%Y%m).json

# Procesar con jq
cat rule_changes_*.json | jq -r '
  .history[] | 
  [.changed_at, .changed_by, .rule_id, .action] | 
  @csv
' > report.csv
```

---

## 🎨 Integración con Dashboard (Futuro)

### Panel de Historial

```javascript
// Nuevo componente en el dashboard
async function loadRuleHistory(ruleId) {
  const response = await fetch(
    `/api/rules/history?rule_id=${ruleId}`,
    { headers: { 'X-API-Key': API_KEY } }
  );
  const data = await response.json();
  
  // Mostrar timeline de cambios
  renderHistoryTimeline(data.history);
}

// Botón de rollback
async function rollbackChange(historyId) {
  if (!confirm('¿Revertir este cambio?')) return;
  
  const response = await fetch(
    `/api/rules/history/${historyId}/rollback`,
    { 
      method: 'POST',
      headers: { 'X-API-Key': API_KEY }
    }
  );
  
  if (response.ok) {
    alert('Cambio revertido exitosamente');
    loadAllRules(); // Recargar reglas
  }
}
```

### UI Propuesta

```
┌─────────────────────────────────────────────────────────┐
│ Historial de Cambios: deployment_sequence_validation   │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ ● 2026-05-04 16:45 - maria.garcia                     │
│   Desactivó la regla                                   │
│   [Revertir] [Ver detalles]                           │
│                                                         │
│ ● 2026-05-04 15:30 - juan.perez                       │
│   Cambió severidad: error → warning                    │
│   [Revertir] [Ver detalles]                           │
│                                                         │
│ ● 2026-05-03 10:15 - admin                            │
│   Creó la regla                                        │
│   [Ver detalles]                                       │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 🔐 Seguridad y Privacidad

### Información Registrada

✅ **Se registra:**
- ID de la regla
- Tipo de cambio
- Valores antes/después
- Usuario (si se proporciona)
- IP del cliente
- Timestamp

❌ **NO se registra:**
- Contraseñas
- Tokens de API
- Información personal sensible

### Retención de Datos

**Recomendaciones:**
- Mantener historial por 90 días mínimo
- Archivar registros antiguos
- Implementar rotación de logs

**Script de limpieza (futuro):**
```sql
-- Eliminar registros mayores a 1 año
DELETE FROM rule_history 
WHERE changed_at < datetime('now', '-1 year');
```

---

## 📈 Métricas y Análisis

### Métricas Disponibles

1. **Total de cambios**
2. **Cambios por tipo de acción**
3. **Cambios por tipo de regla**
4. **Cambios en últimas 24 horas**
5. **Usuarios más activos**
6. **Reglas más modificadas**

### Dashboard de Métricas (Futuro)

```
┌─────────────────────────────────────────┐
│ Estadísticas de Cambios en Reglas      │
├─────────────────────────────────────────┤
│                                         │
│ Total de cambios:        145           │
│ Cambios hoy:             7             │
│ Cambios esta semana:     23            │
│                                         │
│ Por acción:                            │
│   ▓▓▓▓▓▓▓▓ Update (45%)               │
│   ▓▓▓▓ Toggle (25%)                   │
│   ▓▓▓ Create (20%)                    │
│   ▓ Delete (10%)                      │
│                                         │
│ Usuarios más activos:                  │
│   1. juan.perez (34 cambios)          │
│   2. maria.garcia (28 cambios)        │
│   3. admin (15 cambios)               │
│                                         │
└─────────────────────────────────────────┘
```

---

## ✅ Checklist de Implementación

- [x] Crear tabla `rule_history` en SQLite
- [x] Implementar `log_rule_change()`
- [x] Implementar `get_rule_history()`
- [x] Implementar `get_rule_history_stats()`
- [x] Implementar `rollback_rule_change()`
- [x] Modificar `update_branch_rule()` para registrar cambios
- [x] Modificar `create_custom_rule()` para registrar cambios
- [x] Modificar `update_custom_rule()` para registrar cambios
- [x] Modificar `delete_custom_rule()` para registrar cambios
- [x] Modificar `toggle_rule()` para registrar cambios
- [x] Agregar endpoint GET `/api/rules/history`
- [x] Agregar endpoint GET `/api/rules/history/stats`
- [x] Agregar endpoint POST `/api/rules/history/{id}/rollback`
- [x] Pasar `changed_by` e `ip_address` desde endpoints
- [ ] Agregar UI en dashboard para ver historial
- [ ] Agregar botón de rollback en UI
- [ ] Agregar panel de estadísticas
- [ ] Documentar en Notion
- [ ] Capacitar al equipo

---

## 🚀 Próximos Pasos

### Fase 1: Testing (Hoy)
```bash
# 1. Probar creación de regla
curl -X POST -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -H "X-User-Name: test_user" \
  -d '{"id":"test_rule","name":"Test","type":"file_pattern"}' \
  http://localhost:5000/api/rules/custom

# 2. Ver historial
curl -H "X-API-Key: $API_KEY" \
  http://localhost:5000/api/rules/history

# 3. Probar rollback
curl -X POST -H "X-API-Key: $API_KEY" \
  http://localhost:5000/api/rules/history/1/rollback
```

### Fase 2: UI (Mañana)
- Agregar tab "Historial" en modal de reglas
- Mostrar timeline de cambios
- Botón de rollback con confirmación

### Fase 3: Análisis (Esta Semana)
- Dashboard de métricas
- Reportes automáticos
- Alertas de cambios sospechosos

---

## 📞 Soporte

### Comandos Útiles

```bash
# Ver estructura de la tabla
sqlite3 ../memoria/state.db ".schema rule_history"

# Ver últimos 10 cambios
sqlite3 ../memoria/state.db \
  "SELECT * FROM rule_history ORDER BY changed_at DESC LIMIT 10"

# Contar cambios por usuario
sqlite3 ../memoria/state.db \
  "SELECT changed_by, COUNT(*) as count FROM rule_history GROUP BY changed_by"

# Backup de historial
sqlite3 ../memoria/state.db \
  ".output rule_history_backup.sql" \
  ".dump rule_history"
```

---

## 🎉 Beneficios

✅ **Auditoría Completa** - Saber quién cambió qué y cuándo
✅ **Rollback Fácil** - Revertir cambios problemáticos en segundos
✅ **Análisis de Patrones** - Identificar reglas problemáticas
✅ **Cumplimiento** - Satisfacer requisitos de auditoría
✅ **Confianza** - Experimentar sin miedo a romper cosas
✅ **Aprendizaje** - Ver cómo evolucionan las reglas

---

**¡El sistema de historial está listo para usar!** 🚀
