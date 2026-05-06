# 🔍 Diagnóstico: Mensaje "Aprobado" No Llega

**Fecha**: 6 de Mayo, 2026  
**Problema**: El mensaje "✅ Aprobado" no está llegando a Slack  
**Estado**: 🔍 **EN DIAGNÓSTICO**

---

## 🚨 Problema Reportado

> "¿Qué está pasando con el mensaje de aprobado que no lo está mandando?"

El mensaje "✅ Aprobado" no está llegando al thread del PR en Slack.

---

## 🔍 Causa Probable

El código busca el **thread del PR** en Slack usando el patrón:

```python
needle = f"pullrequest/{pr_id}"
```

**Si no encuentra el thread**, no puede enviar el mensaje.

---

## 📋 Posibles Causas

### 1. El PR No Tiene Mensaje Inicial en Slack

**Síntoma**: El PR nunca tuvo un mensaje en Slack

**Solución**: 
- Verificar que Azure DevOps esté configurado para enviar notificaciones a Slack
- O crear manualmente el mensaje inicial del PR

### 2. El Patrón de Búsqueda No Coincide

**Síntoma**: Los mensajes de PR en Slack usan un formato diferente

**Ejemplos de formatos posibles**:
- `pullrequest/123` ← Actual
- `pull request #123`
- `PR #123`
- `https://.../_git/.../pullrequest/123`

**Solución**: Ajustar el patrón de búsqueda

### 3. El Thread Está Más Allá de los Últimos 200 Mensajes

**Síntoma**: El canal es muy activo y el mensaje del PR ya no está en los últimos 200

**Solución**: Aumentar el límite de búsqueda o usar cache

### 4. El Thread Ya Está en Cache Pero Es Incorrecto

**Síntoma**: El sistema tiene un thread_ts guardado pero es incorrecto

**Solución**: Limpiar el cache de threads

---

## 🛠️ Diagnóstico Paso a Paso

### Paso 1: Ver Mensajes del Canal

Ejecuta el script de diagnóstico:

```bash
source venv/bin/activate
python debug_slack_messages.py --limit 50
```

**Esto mostrará**:
- Los últimos 50 mensajes del canal
- El texto de cada mensaje
- Los patrones encontrados (pullrequest/, PR #, etc.)
- Los threads disponibles

**Busca**:
- Mensajes que correspondan a PRs
- Qué patrón usan (ej: "pullrequest/123", "PR #123", etc.)
- Si tienen thread_ts

### Paso 2: Identificar el Patrón Correcto

Una vez que veas los mensajes, identifica el patrón que usan.

**Ejemplos**:

Si ves algo como:
```
Texto: New pull request: PR #123 - Fix bug
Link: https://dev.azure.com/.../pullrequest/123
```

El patrón podría ser:
- `PR #123`
- `pullrequest/123`
- Ambos

### Paso 3: Ajustar el Código

Si el patrón es diferente, necesitamos ajustar `find_pr_thread()` en `integrations/slack.py`.

**Ejemplo**: Si el patrón es `PR #123`:

```python
# ANTES
needle = f"pullrequest/{pr_id}"

# DESPUÉS
needle = f"PR #{pr_id}"
# O buscar ambos:
needles = [f"pullrequest/{pr_id}", f"PR #{pr_id}"]
```

### Paso 4: Limpiar Cache de Threads (Si Es Necesario)

Si el cache tiene threads incorrectos:

```python
# En Python console o script
from integrations.state import load_state, save_state

state = load_state()
state["pr_threads"] = {}  # Limpiar cache de threads
save_state(state)
```

---

## 🔧 Soluciones Temporales

### Opción 1: Enviar Mensaje Directo al Canal (Sin Thread)

Si no puedes encontrar el thread, puedes modificar temporalmente el código para enviar al canal directamente:

```python
# En notify_pr_slack(), cambiar:
slack_api("chat.postMessage", {"channel": channel, "text": text})
# En lugar de:
slack_api("chat.postMessage", {"channel": channel, "text": text, "thread_ts": thread_ts})
```

**Nota**: Esto enviará el mensaje al canal principal, no al thread del PR.

### Opción 2: Crear Thread Manualmente

Si sabes el timestamp del mensaje del PR, puedes agregarlo manualmente al cache:

```python
from integrations.state import load_state, save_state

state = load_state()
pr_threads = state.setdefault("pr_threads", {})
pr_threads["123"] = "1778074353.566779"  # Reemplaza con el timestamp real
save_state(state)
```

---

## 📊 Logs para Revisar

Cuando apruebas un PR, busca estos logs:

### Logs Esperados (Éxito)

```
[INFO] [approve] PR 123 aprobado y notificado
[INFO] [slack] Notificación enviada PR 123 acción approve
```

### Logs de Problema

```
[WARNING] [slack] No se pudo notificar PR 123 (acción: approve): hilo no encontrado
```

O:

```
[INFO] [slack] Notificación duplicada ignorada PR 123 acción approve (ya enviada anteriormente)
```

---

## 🧪 Prueba Manual

### Verificar que Slack Funciona

```bash
# Enviar mensaje de prueba al canal (SIN thread)
curl -X POST https://slack.com/api/chat.postMessage \
  -H "Authorization: Bearer xoxp-2013094397781-9421813286548-11011293944550-d94e504daa609067068f604c093b4019" \
  -H "Content-Type: application/json" \
  -d '{"channel":"C080K9D6EG2","text":"🧪 Test manual - verificando conexión"}'
```

**Resultado esperado**: Mensaje aparece en el canal

### Buscar Thread de un PR Específico

```bash
# Reemplaza 123 con el ID del PR
python -c "
from integrations.slack import find_pr_thread
thread_ts = find_pr_thread(123)
print(f'Thread encontrado: {thread_ts}' if thread_ts else 'Thread NO encontrado')
"
```

---

## 📋 Checklist de Diagnóstico

- [ ] Ejecutar `debug_slack_messages.py` para ver mensajes del canal
- [ ] Identificar el patrón que usan los mensajes de PR
- [ ] Verificar si el patrón coincide con `pullrequest/{pr_id}`
- [ ] Si no coincide, ajustar el código
- [ ] Limpiar cache de threads si es necesario
- [ ] Probar envío manual de mensaje
- [ ] Revisar logs del servidor
- [ ] Verificar que el PR tenga un mensaje inicial en Slack

---

## 🎯 Próxima Acción

**Ejecuta el script de diagnóstico**:

```bash
source venv/bin/activate
python debug_slack_messages.py --limit 50
```

**Luego dime**:
1. ¿Ves mensajes de PRs en la salida?
2. ¿Qué patrón usan? (ej: "pullrequest/123", "PR #123", etc.)
3. ¿Tienen thread_ts?

Con esa información puedo ajustar el código para que encuentre correctamente los threads.

---

## 💡 Alternativa: Usar URL del PR

Si los mensajes contienen la URL completa del PR, podríamos buscar por eso:

```python
# En lugar de:
needle = f"pullrequest/{pr_id}"

# Usar:
needle = f"pullrequest/{pr_id}"  # Busca en la URL
```

Esto funcionaría si los mensajes tienen links como:
`https://dev.azure.com/OrgClaroColombia/SalesForce/_git/SalesForce/pullrequest/123`

---

**Estado**: 🔍 **Esperando información del diagnóstico**

Ejecuta el script y comparte los resultados para que pueda ajustar el código.
