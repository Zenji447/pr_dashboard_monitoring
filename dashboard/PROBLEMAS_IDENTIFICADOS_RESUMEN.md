# 📋 Problemas Identificados - Resumen

**Fecha**: 6 de Mayo, 2026  
**Sesión**: Debugging de Slack y Veredictos

---

## 🚨 Problema 1: Mensaje "Aprobado" No Llega

### Causa Raíz
El PR 88357 está en `approved_notified`, lo que significa que ya fue procesado pero la notificación falló (probablemente no encontró el thread).

### Por Qué Falló
Cuando aprobaste el PR:
1. El sistema lo marcó como "aprobado" en `approved_notified`
2. Intentó enviar la notificación a Slack
3. No encontró el thread del PR (probablemente porque `find_pr_thread` no pudo leer los mensajes del canal)
4. La notificación falló pero el PR quedó marcado como "ya aprobado"
5. Ahora no volverá a intentar enviar la notificación

### Solución
```bash
# Limpiar el guard para ese PR
python3 check_slack_guard.py --clean 88357

# Luego vuelve a aprobar desde el dashboard
```

### Solución Permanente
El problema real es que `find_pr_thread()` no está encontrando los threads. Posibles causas:

1. **El patrón de búsqueda no coincide**: El código busca `pullrequest/{pr_id}` pero los mensajes pueden usar otro formato
2. **Permisos del token**: El token `xoxp-` (user token) puede tener limitaciones en canales privados compartidos
3. **Los mensajes están más allá de los últimos 200**: El límite de búsqueda es 200 mensajes

**Recomendación**: Necesitamos ver un mensaje real de PR en Slack para ajustar el patrón de búsqueda.

---

## 🚨 Problema 2: Veredicto No Se Actualiza

### Causa Raíz
El veredicto se calcula cuando se **obtienen los PRs**, no cuando se aprueba.

### Flujo Actual
```
1. Usuario aprueba PR
   ↓
2. Backend marca como aprobado
   ↓
3. Backend invalida cache de PRs
   ↓
4. Frontend sigue mostrando datos antiguos
   ↓
5. Usuario necesita refrescar manualmente
```

### Solución Temporal
**Refrescar la página** después de aprobar.

### Solución Permanente
Hay dos opciones:

#### Opción A: Frontend Auto-Refresh
Modificar el frontend para que refresque automáticamente después de aprobar:

```javascript
// En el frontend, después de aprobar:
fetch('/api/pr/123/approve', {method: 'POST'})
  .then(() => {
    // Refrescar lista de PRs
    fetchPRs();
  });
```

#### Opción B: Retornar PR Actualizado
Modificar el endpoint `/approve` para que retorne el PR actualizado:

```python
@app.route("/api/pr/<int:pr_id>/approve", methods=["POST"])
def approve(pr_id):
    # ... aprobar ...
    
    # Invalidar cache
    invalidate_prs_cache()
    
    # Obtener PR actualizado
    prs = get_prs()
    updated_pr = next((pr for pr in prs if pr["id"] == pr_id), None)
    
    return jsonify({"ok": True, "pr": updated_pr})
```

---

## 🚨 Problema 3: find_pr_thread() No Encuentra Threads

### Causa Raíz
El código busca el patrón `pullrequest/{pr_id}` pero:
1. Los mensajes pueden usar otro formato
2. El canal privado compartido puede tener limitaciones de lectura
3. Los mensajes están más allá de los últimos 200

### Evidencia
```bash
python3 -c "from integrations.slack import slack_api; print(slack_api('conversations.history', {'channel': 'C080K9D6EG2', 'limit': 200}).get('messages', []))"
# Resultado: []  ← No se pueden leer mensajes
```

### Solución
Necesitamos diagnosticar por qué no se pueden leer los mensajes:

1. **Verificar permisos del token**:
   - El token necesita el scope `channels:history`
   - Para canales privados, necesita `groups:history`

2. **Usar Bot Token en lugar de User Token**:
   - Los Bot Tokens (`xoxb-`) suelen tener mejores permisos
   - Los User Tokens (`xoxp-`) pueden tener limitaciones

3. **Verificar que el usuario/bot esté en el canal**:
   - El token debe pertenecer a un usuario/bot que esté en el canal

### Diagnóstico
```bash
# Ver permisos del token
curl -X POST https://slack.com/api/auth.test \
  -H "Authorization: Bearer TOKEN"

# Ver scopes del token
curl -X POST https://slack.com/api/apps.permissions.info \
  -H "Authorization: Bearer TOKEN"
```

---

## 📊 Resumen de Estado

### ✅ Funcionando
- Token de Slack configurado
- Canal de Slack configurado
- Mensajes "PR integrado" llegan
- Mensajes "Despliegue completado" llegan
- Auto-complete funciona

### ❌ No Funcionando
- Mensaje "✅ Aprobado" no llega
- Veredicto no se actualiza en tiempo real
- `find_pr_thread()` no encuentra threads

### 🔍 Necesita Investigación
- Por qué `conversations.history` retorna 0 mensajes
- Qué permisos tiene el token actual
- Qué formato usan los mensajes de PR en Slack

---

## 🎯 Próximos Pasos

### Paso 1: Limpiar Guard y Probar
```bash
python3 check_slack_guard.py --clean 88357
# Luego aprobar desde el dashboard
```

### Paso 2: Diagnosticar Permisos de Slack
```bash
# Ver info del token
curl -X POST https://slack.com/api/auth.test \
  -H "Authorization: Bearer xoxp-2013094397781-9421813286548-11011293944550-d94e504daa609067068f604c093b4019"
```

### Paso 3: Ver Mensajes del Canal (Manualmente)
- Abre Slack
- Ve al canal `proj-claroco-devops-requests`
- Busca un mensaje de PR
- Copia el texto completo
- Identifica qué patrón usa (ej: "pullrequest/123", "PR #123", etc.)

### Paso 4: Ajustar Código
Una vez que sepamos el patrón correcto, ajustar `find_pr_thread()` en `integrations/slack.py`.

---

## 📝 Archivos Creados

1. `check_slack_guard.py` - Script para verificar y limpiar guards
2. `debug_slack_messages.py` - Script para ver mensajes del canal
3. `PROBLEMAS_IDENTIFICADOS_RESUMEN.md` - Este archivo

---

## 💡 Recomendaciones

### Corto Plazo
1. Limpiar guard del PR 88357 y volver a aprobar
2. Refrescar página después de aprobar para ver veredicto actualizado

### Mediano Plazo
1. Investigar por qué `conversations.history` no retorna mensajes
2. Considerar usar Bot Token en lugar de User Token
3. Ajustar patrón de búsqueda de threads

### Largo Plazo
1. Implementar auto-refresh en frontend
2. Mejorar manejo de errores en notificaciones
3. Agregar retry automático si falla la notificación

---

**Estado**: 🔍 **Problemas identificados, soluciones propuestas**

Ejecuta los pasos de diagnóstico y comparte los resultados.
