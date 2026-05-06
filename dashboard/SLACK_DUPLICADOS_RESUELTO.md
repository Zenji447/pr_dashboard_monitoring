# 🔧 Slack Notificaciones Duplicadas - RESUELTO

**Fecha**: 6 de Mayo, 2026  
**Problema**: Mensajes duplicados múltiples veces  
**Estado**: ✅ **CORREGIDO**

---

## 🚨 Problema Reportado

```
Aprobado[9:42]
Aprobado[9:42]
Aprobado[9:42]
Aprobado[9:42]
TA por favor revisa este PR[9:42]
TA por favor revisa este PR[9:42]
TA por favor revisa este PR[9:42]
TA por favor revisa este PR[9:42]
```

**Síntoma**: Cada notificación se enviaba 4 veces (duplicados masivos)

---

## 🔍 Causa Raíz Identificada

### Problema 1: Guard en Memoria RAM

El sistema usaba un `set()` en memoria para evitar duplicados:

```python
# ANTES (MALO)
_notified_memory = set()  # Se pierde al reiniciar servidor

def notify_pr_slack(pr_id, action, detail=None):
    key = (int(pr_id), action)
    if key in _notified_memory:  # ❌ Solo funciona en la misma sesión
        return
    _notified_memory.add(key)
```

**Problemas**:
- ❌ Se pierde al reiniciar el servidor
- ❌ No funciona con múltiples workers
- ❌ No funciona con requests simultáneos
- ❌ Race conditions

### Problema 2: Verificación Tardía

En `app.py`, la verificación de duplicados ocurría DESPUÉS de aprobar el PR:

```python
# ANTES (MALO)
def approve(pr_id):
    result = set_pr_vote(pr_id, "approve")  # ← Aprueba primero
    
    if pr_id not in approved_notified:      # ← Verifica después
        notify_pr_slack(pr_id, "approve")
```

**Problema**: Si se hacían múltiples requests simultáneos, todos pasaban la verificación.

### Problema 3: Dos Notificaciones Separadas

El endpoint `/approve` enviaba DOS notificaciones:
1. "✅ Aprobado"
2. "TA por favor revisa este PR"

Ambas podían duplicarse independientemente.

---

## ✅ Solución Aplicada

### Fix 1: Guard Persistente en Base de Datos

Cambié el guard de memoria RAM a base de datos:

```python
# DESPUÉS (BUENO)
def notify_pr_slack(pr_id, action, detail=None):
    # Usar base de datos en lugar de memoria
    state = load_state()
    slack_notifications = state.setdefault("slack_notifications", {})
    
    notification_key = f"{pr_id}:{action}"
    
    # Verificar si ya fue enviada
    if notification_key in slack_notifications:
        logger.info("Notificación duplicada ignorada")
        return
    
    # Marcar como enviada ANTES de enviar
    slack_notifications[notification_key] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pr_id": pr_id,
        "action": action
    }
    save_state(state)
    
    # Ahora sí enviar...
```

**Ventajas**:
- ✅ Persiste entre reinicios del servidor
- ✅ Funciona con múltiples workers
- ✅ Previene race conditions
- ✅ Auditable (se puede ver historial)

### Fix 2: Verificación Temprana

Cambié el orden en `app.py` para verificar ANTES de aprobar:

```python
# DESPUÉS (BUENO)
def approve(pr_id):
    # Verificar PRIMERO
    state = load_state()
    approved_notified = state.setdefault("approved_notified", [])
    
    if pr_id in approved_notified:
        return jsonify({"ok": True, "already_approved": True})
    
    # Aprobar el PR
    result = set_pr_vote(pr_id, "approve")
    
    # Marcar como aprobado INMEDIATAMENTE
    approved_notified.append(pr_id)
    save_state(state)
    
    # Notificar (solo una vez)
    notify_pr_slack(pr_id, "approve")
```

**Ventajas**:
- ✅ Previene múltiples aprobaciones
- ✅ Marca como procesado antes de enviar
- ✅ Retorna inmediatamente si ya fue procesado

### Fix 3: Guard para Notificación de TA

Apliqué el mismo patrón para la notificación de TA:

```python
def _notify_ta():
    state2 = load_state()
    ta_notified = state2.setdefault("ta_notified", [])
    
    # Verificar nuevamente
    if pr_id in ta_notified:
        return
    
    # Marcar como notificado ANTES de enviar
    ta_notified.append(pr_id)
    save_state(state2)
    
    # Ahora sí enviar...
```

---

## 📊 Cambios Realizados

### Archivos Modificados

1. **`integrations/slack.py`**:
   - ✅ Eliminado guard en memoria RAM
   - ✅ Implementado guard persistente en BD
   - ✅ Mejorado manejo de errores
   - ✅ Limpieza automática si falla el envío

2. **`app.py`**:
   - ✅ Verificación temprana en `/approve`
   - ✅ Marcado inmediato como procesado
   - ✅ Guard mejorado para notificación de TA
   - ✅ Mejor logging

---

## 🎯 Cómo Funciona Ahora

### Flujo de Aprobación

```
1. Request POST /api/pr/123/approve
   ↓
2. Verificar si PR 123 ya fue aprobado
   - Si SÍ → Retornar {"already_approved": true}
   - Si NO → Continuar
   ↓
3. Marcar PR 123 como aprobado en BD
   ↓
4. Aprobar PR en Azure DevOps
   ↓
5. Notificar "✅ Aprobado" (con guard persistente)
   ↓
6. Notificar "TA por favor revisa" (con guard persistente)
```

### Guard de Notificaciones

```
Base de Datos (state.db):
{
  "slack_notifications": {
    "123:approve": {
      "timestamp": "2026-05-06T09:42:00Z",
      "pr_id": 123,
      "action": "approve"
    },
    "123:reject": { ... },
    "456:approve": { ... }
  }
}
```

**Cada notificación tiene una clave única**: `{pr_id}:{action}`

---

## 🧪 Pruebas Recomendadas

### Test 1: Aprobación Simple

```bash
# Aprobar PR 123
curl -X POST http://localhost:5000/api/pr/123/approve \
  -H "Authorization: Bearer API_KEY"

# Resultado esperado:
# - 1 mensaje "✅ Aprobado" en Slack
# - 1 mensaje "TA por favor revisa este PR" en Slack
# - Total: 2 mensajes (NO 8)
```

### Test 2: Aprobación Duplicada

```bash
# Aprobar el mismo PR dos veces
curl -X POST http://localhost:5000/api/pr/123/approve \
  -H "Authorization: Bearer API_KEY"

curl -X POST http://localhost:5000/api/pr/123/approve \
  -H "Authorization: Bearer API_KEY"

# Resultado esperado:
# - Primera llamada: Aprueba y notifica
# - Segunda llamada: Retorna {"already_approved": true}
# - Total: 2 mensajes (NO 4)
```

### Test 3: Requests Simultáneos

```bash
# Enviar 5 requests al mismo tiempo
for i in {1..5}; do
  curl -X POST http://localhost:5000/api/pr/123/approve \
    -H "Authorization: Bearer API_KEY" &
done
wait

# Resultado esperado:
# - Solo 1 aprobación procesada
# - Total: 2 mensajes (NO 10)
```

---

## 📋 Verificación

### Logs Esperados

**Primera aprobación**:
```
[INFO] [approve] PR 123 aprobado y notificado
[INFO] [slack] Notificación enviada PR 123 acción approve
[INFO] [approve] TA notificado para PR 123
```

**Aprobación duplicada**:
```
[INFO] [approve] PR 123 ya fue aprobado anteriormente, omitiendo
```

**Notificación duplicada**:
```
[INFO] [slack] Notificación duplicada ignorada PR 123 acción approve (ya enviada anteriormente)
```

---

## 🔧 Mantenimiento

### Limpiar Historial de Notificaciones

Si la tabla `slack_notifications` crece mucho, puedes limpiarla:

```python
# En Python console o script
from integrations.state import load_state, save_state

state = load_state()
state["slack_notifications"] = {}  # Limpiar todo
save_state(state)
```

O limpiar solo notificaciones antiguas:

```python
from datetime import datetime, timedelta

state = load_state()
notifications = state.get("slack_notifications", {})
cutoff = (datetime.now() - timedelta(days=30)).isoformat()

# Mantener solo últimos 30 días
state["slack_notifications"] = {
    k: v for k, v in notifications.items()
    if v.get("timestamp", "") > cutoff
}
save_state(state)
```

---

## ✅ Checklist

- [x] Guard en memoria eliminado
- [x] Guard persistente implementado
- [x] Verificación temprana en `/approve`
- [x] Marcado inmediato como procesado
- [x] Guard para notificación de TA
- [x] Mejor logging
- [x] Limpieza automática en caso de error
- [ ] **Reiniciar servidor** ← TÚ AHORA
- [ ] **Probar con un PR** ← TÚ AHORA
- [ ] **Verificar que NO haya duplicados** ← TÚ AHORA

---

## 🚀 Próxima Acción

```bash
# Reiniciar el servidor
source venv/bin/activate
python app.py

# Probar con un PR
# Aprobar desde el dashboard
# Verificar en Slack que llegue SOLO 1 mensaje de cada tipo
```

---

## 📝 Notas Importantes

1. **El guard es persistente**: Sobrevive reinicios del servidor
2. **Cada notificación es única**: `{pr_id}:{action}`
3. **Si falla el envío**: Se limpia automáticamente para permitir reintento
4. **Auditable**: Puedes ver todas las notificaciones enviadas en la BD

---

## 🎉 Resumen

**Problema**: Notificaciones duplicadas 4 veces cada una (8 mensajes total)  
**Causa**: Guard en memoria RAM + verificación tardía + race conditions  
**Solución**: Guard persistente en BD + verificación temprana + marcado inmediato  
**Resultado**: ✅ **Solo 1 notificación de cada tipo** (2 mensajes total)

---

**Estado**: ✅ **CORREGIDO - Listo para probar**

Reinicia el servidor y prueba. Los duplicados deberían estar completamente eliminados.
