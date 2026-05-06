# 🔍 Diagnóstico: Slack No Notifica

**Fecha**: 6 de Mayo, 2026  
**Estado**: ❌ **PROBLEMA IDENTIFICADO**

---

## 🎯 Problema Reportado

> "Estoy viendo un detalle importante y es que no esta notificando por slack"

Usuario reporta que Slack **funcionaba antes** pero ahora no está notificando.

---

## 🔎 Investigación Realizada

### 1. Revisión del Código (`integrations/slack.py`)

**Línea 30** - El código busca el token de Slack:
```python
'bot_token': os.getenv("SLACK_BOT_TOKEN") or os.getenv("SLACK_TOKEN"),
```

✅ **FIX APLICADO**: Ahora busca ambas variables (`SLACK_BOT_TOKEN` y `SLACK_TOKEN`)

### 2. Revisión del Archivo `.env`

**Configuración actual**:
```env
SLACK_BOT_TOKEN=xoxb-your-token-here
SLACK_PR_CHANNEL=C08ABCDEFGH
```

❌ **PROBLEMA**: El token es un **placeholder** (`xoxb-your-token-here`)

### 3. Revisión de la Base de Datos

**Query ejecutada**:
```sql
SELECT tenant_id, integration_type, enabled, config 
FROM tenant_integrations 
WHERE integration_type = 'slack';
```

**Resultado**:
```
tenant_id: 1
integration_type: slack
enabled: 1
config: {"channel": "C08DXXXXXQP", "bot_token": "xoxb-your-token-here"}
```

❌ **PROBLEMA**: El token en la BD también es un **placeholder**

---

## 🚨 Causa Raíz Identificada

### El token de Slack es un placeholder en 2 lugares:

1. **`.env`**: `SLACK_BOT_TOKEN=xoxb-your-token-here`
2. **Base de datos**: `bot_token: "xoxb-your-token-here"`

### ¿Por qué funcionaba antes?

**Hipótesis más probable**: 
- Antes de la migración multi-tenant, el sistema usaba un archivo `../memoria/state.json` que contenía el token real
- Durante la migración, se copió un token placeholder en lugar del token real
- El archivo `../memoria/state.json` (fuera del workspace) probablemente contiene el token real

---

## ✅ Solución Propuesta

### Opción A: Recuperar Token Real (RECOMENDADO)

Si tienes acceso al archivo `../memoria/state.json` o backups:

1. **Buscar el token real** en archivos antiguos
2. **Actualizar `.env`**:
   ```env
   SLACK_BOT_TOKEN=xoxb-REAL-TOKEN-AQUI
   SLACK_PR_CHANNEL=C08DXXXXXQP
   ```
3. **Actualizar base de datos**:
   ```sql
   UPDATE tenant_integrations 
   SET config = json_set(config, '$.bot_token', 'xoxb-REAL-TOKEN-AQUI') 
   WHERE tenant_id = 1 AND integration_type = 'slack';
   ```
4. **Reiniciar servidor**

### Opción B: Obtener Nuevo Token

Si no encuentras el token real:

1. **Ir a**: https://api.slack.com/apps
2. **Seleccionar tu app** (o crear una nueva)
3. **Ir a**: OAuth & Permissions
4. **Copiar**: Bot User OAuth Token (empieza con `xoxb-`)
5. **Permisos necesarios**:
   - `chat:write` - Enviar mensajes
   - `channels:history` - Leer historial de canales
   - `channels:read` - Ver información de canales
6. **Aplicar pasos de Opción A** con el nuevo token

### Opción C: Deshabilitar Slack Temporalmente

Si no necesitas Slack ahora:

```sql
UPDATE tenant_integrations 
SET enabled = 0 
WHERE tenant_id = 1 AND integration_type = 'slack';
```

---

## 🔧 Verificación del Canal

También necesitas verificar que el canal sea correcto:

**En `.env`**:
```env
SLACK_PR_CHANNEL=C08ABCDEFGH  # ← ¿Es este el canal correcto?
```

**En base de datos**:
```json
{"channel": "C08DXXXXXQP"}  # ← ¿Es este el canal correcto?
```

**Nota**: Hay una discrepancia entre `.env` y la BD:
- `.env`: `C08ABCDEFGH`
- BD: `C08DXXXXXQP`

### Cómo obtener el ID del canal correcto:

1. Abre Slack
2. Ve al canal donde quieres las notificaciones
3. Click en el nombre del canal (arriba)
4. Scroll hasta abajo
5. Copia el "Channel ID" (empieza con `C`)

---

## 📋 Checklist de Solución

### Paso 1: Obtener Token Real
- [ ] Buscar en `../memoria/state.json` (fuera del workspace)
- [ ] Buscar en backups
- [ ] O generar nuevo token en https://api.slack.com/apps

### Paso 2: Verificar Canal
- [ ] Confirmar ID del canal correcto en Slack
- [ ] Decidir cuál usar: `C08ABCDEFGH` o `C08DXXXXXQP`

### Paso 3: Actualizar Configuración
- [ ] Actualizar `.env` con token real y canal correcto
- [ ] Actualizar base de datos con token real y canal correcto

### Paso 4: Reiniciar y Probar
- [ ] Reiniciar servidor: `python app.py`
- [ ] Probar notificación con un PR de prueba
- [ ] Verificar que llegue mensaje a Slack

---

## 🎯 Comando para Actualizar BD

Una vez que tengas el token real:

```bash
# Reemplaza TOKEN_REAL y CANAL_REAL con los valores correctos
sqlite3 ../memoria/state.db "UPDATE tenant_integrations SET config = json_set(config, '$.bot_token', 'TOKEN_REAL', '$.channel', 'CANAL_REAL') WHERE tenant_id = 1 AND integration_type = 'slack';"
```

---

## 📝 Notas Adicionales

### El código ya está preparado para funcionar

El fix aplicado en `integrations/slack.py` línea 30 hace que el código busque el token en:
1. Variable de entorno `SLACK_BOT_TOKEN`
2. Variable de entorno `SLACK_TOKEN` (fallback)
3. Configuración del tenant en la base de datos

### Prioridad de configuración

El sistema usa esta prioridad:
1. **Primero**: Config del tenant en BD (si existe y está habilitado)
2. **Fallback**: Variables de entorno (`.env`)

### Logs para debugging

Para ver qué está pasando, revisa los logs cuando se intenta enviar una notificación:
```python
logger.debug("Slack no está habilitado para este tenant, omitiendo notificación")
logger.warning("No hay token de Slack configurado")
logger.info("[slack] Notificación enviada PR %s acción %s", pr_id, action)
logger.error("[slack] Error notificando PR %s: %s", pr_id, e)
```

---

## 🚀 Próxima Acción

**¿Qué necesitas?**

1. **"buscar token"** → Te ayudo a buscar el token en archivos del sistema
2. **"nuevo token"** → Te guío para obtener uno nuevo de Slack
3. **"deshabilitar"** → Deshabilitamos Slack temporalmente
4. **"tengo el token"** → Te ayudo a configurarlo

---

**Estado**: Esperando tu decisión sobre cómo proceder 🎯
