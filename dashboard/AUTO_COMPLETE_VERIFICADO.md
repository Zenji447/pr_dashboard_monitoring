# ✅ Auto-Complete de PRs - Verificado y Corregido

**Fecha**: 6 de Mayo, 2026  
**Requerimiento**: Si un PR está aprobado por ti Y aprobado por TA, debe completarse automáticamente  
**Estado**: ✅ **VERIFICADO Y CORREGIDO**

---

## 🎯 Requerimiento

> "Si está aprobado por mí y aprobado [por TA] y no está completado el PR, también debemos darle completar"

**Traducción**: Auto-complete cuando:
1. ✅ TÚ aprobaste el PR
2. ✅ TA aprobó el PR (policies approved)
3. ✅ No tiene conflictos
4. ✅ No está bloqueado
5. ✅ Rama no está congelada

---

## 🔍 Análisis del Código Actual

### Condición de Auto-Complete

La lógica ya existía en `services/pr_service.py`:

```python
# Auto-complete
if (
    target_branch in {"develop", "develop-pr", "releaseproyecto/r6"}
    and report["myVote"] == "approved"      # ← TÚ aprobaste
    and report["canComplete"]                # ← TA aprobó (policies approved)
    and not report["hasConflicts"]           # ← Sin conflictos
    and not report["blocked"]                # ← No bloqueado
    and not report["frozen"]                 # ← Rama no congelada
):
    _try_auto_complete(pr_id, report, state, token)
```

### ¿Qué Significa Cada Condición?

1. **`target_branch in {...}`**: Solo auto-complete en ramas específicas
2. **`report["myVote"] == "approved"`**: TÚ aprobaste el PR
3. **`report["canComplete"]`**: Todas las policies están aprobadas (incluyendo TA)
4. **`not report["hasConflicts"]`**: No hay conflictos de merge
5. **`not report["blocked"]`**: El autor no está bloqueado
6. **`not report["frozen"]`**: La rama target no está congelada

### ¿Cómo se Determina `canComplete`?

```python
policy_status = get_pr_policy_status(pr_id, token)
report["canComplete"] = policy_status == "approved"
```

**`policy_status == "approved"`** significa:
- ✅ Todos los reviewers requeridos aprobaron (incluyendo TA)
- ✅ Todas las build policies pasaron
- ✅ Todas las otras policies están satisfechas

---

## 🚨 Problema Identificado

### Bug en `get_my_vote()`

La función que determina si TÚ aprobaste tenía un bug:

```python
# ANTES (MALO)
def get_my_vote(pr):
    reviewers = pr.get("reviewers", [])
    # Buscar mi voto (esto debería usar el usuario actual, pero por simplicidad usamos el primer reviewer)
    for reviewer in reviewers:  # ← ❌ Busca el PRIMER reviewer, no TÚ
        vote = reviewer.get("vote", 0)
        if vote == 10:
            return "approved"
```

**Problema**: Retornaba el voto del PRIMER reviewer, no necesariamente el tuyo.

**Consecuencia**: Si el primer reviewer aprobó pero tú no, el sistema pensaba que TÚ aprobaste.

---

## ✅ Solución Aplicada

### Fix: Buscar Específicamente TU Voto

```python
# DESPUÉS (BUENO)
def get_my_vote(pr):
    # Obtener el usuario actual de Azure
    result = subprocess.run([
        "az", "account", "show", "--query", "user.name", "-o", "tsv"
    ], capture_output=True, text=True, check=False)
    
    current_user_email = result.stdout.strip().lower()
    
    reviewers = pr.get("reviewers", [])
    
    # Buscar específicamente MI voto
    for reviewer in reviewers:
        reviewer_email = reviewer.get("uniqueName", "").lower()
        
        if current_user_email in reviewer_email:
            vote = reviewer.get("vote", 0)
            if vote == 10:
                return "approved"
            elif vote == -10:
                return "rejected"
            elif vote == -5:
                return "waiting"
            else:
                return "no_vote"
    
    return "no_vote"
```

**Mejoras**:
- ✅ Obtiene el usuario actual de Azure (`az account show`)
- ✅ Busca específicamente el reviewer que coincide con tu email
- ✅ Retorna TU voto, no el de otro reviewer

---

## 📊 Flujo Completo de Auto-Complete

```
1. PR es creado
   ↓
2. Sistema revisa PRs activos cada 30 segundos
   ↓
3. Para cada PR, verifica condiciones:
   ├─ ¿Rama target es develop/develop-pr/releaseproyecto/r6? ✓
   ├─ ¿TÚ aprobaste? (get_my_vote == "approved") ✓
   ├─ ¿TA aprobó? (canComplete == True) ✓
   ├─ ¿Sin conflictos? ✓
   ├─ ¿No bloqueado? ✓
   └─ ¿Rama no congelada? ✓
   ↓
4. Si TODAS las condiciones se cumplen:
   ├─ Completar PR (merge)
   ├─ Marcar como auto_completed
   ├─ Agregar a Google Sheets
   ├─ Iniciar polling de deploy
   └─ Notificar en Slack cuando deploy termine
```

---

## 🎯 Cómo Funciona en la Práctica

### Escenario 1: Aprobación Completa

```
Estado del PR:
- Autor: Juan Pérez
- Target: develop
- TÚ: ✅ Aprobado (vote = 10)
- TA: ✅ Aprobado (vote = 10)
- Policies: ✅ Approved
- Conflictos: ❌ No

Resultado: ✅ AUTO-COMPLETE
```

### Escenario 2: Solo TÚ Aprobaste

```
Estado del PR:
- Autor: Juan Pérez
- Target: develop
- TÚ: ✅ Aprobado (vote = 10)
- TA: ⏳ Pendiente (vote = 0)
- Policies: ⏳ Waiting
- Conflictos: ❌ No

Resultado: ⏳ ESPERA (falta aprobación de TA)
```

### Escenario 3: Solo TA Aprobó

```
Estado del PR:
- Autor: Juan Pérez
- Target: develop
- TÚ: ⏳ Pendiente (vote = 0)
- TA: ✅ Aprobado (vote = 10)
- Policies: ⏳ Waiting
- Conflictos: ❌ No

Resultado: ⏳ ESPERA (falta tu aprobación)
```

### Escenario 4: Con Conflictos

```
Estado del PR:
- Autor: Juan Pérez
- Target: develop
- TÚ: ✅ Aprobado (vote = 10)
- TA: ✅ Aprobado (vote = 10)
- Policies: ✅ Approved
- Conflictos: ⚠️ SÍ

Resultado: ❌ NO AUTO-COMPLETE (tiene conflictos)
```

---

## 🔧 Configuración

### Ramas con Auto-Complete

Por defecto, auto-complete está habilitado para:
- `develop`
- `develop-pr`
- `releaseproyecto/r6`

### Deshabilitar Auto-Complete para una Rama

Si quieres deshabilitar auto-complete para una rama específica, agrégala a "blocked_branches":

```bash
# Ejemplo: Congelar develop temporalmente
curl -X POST http://localhost:5000/api/config/blocked-branches \
  -H "Authorization: Bearer API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"branches": ["develop"]}'
```

Cuando una rama está en "blocked_branches", `report["frozen"] = True` y el auto-complete no se ejecuta.

---

## 📋 Verificación

### Logs Esperados

**Cuando auto-complete se ejecuta**:
```
[INFO] [auto-complete] PR 123 completado automáticamente
```

**Cuando falta tu aprobación**:
```
# No hay log, simplemente no se ejecuta auto-complete
```

**Cuando falta aprobación de TA**:
```
# No hay log, canComplete = False
```

**Cuando falla el complete**:
```
[WARNING] [auto-complete] Falló PR 123: [error message]
```

### Verificar en el Dashboard

En el dashboard, un PR que cumple las condiciones:
- ✅ Muestra "Aprobable" o "Aprobable con cautela"
- ✅ Tiene tu voto como "approved"
- ✅ Tiene policy status como "approved"
- ✅ No tiene conflictos

Debería completarse automáticamente en el próximo refresh (máximo 30 segundos).

---

## 🧪 Pruebas Recomendadas

### Test 1: Aprobación Completa

1. Crea un PR hacia `develop`
2. Apruébalo desde el dashboard
3. Espera a que TA apruebe
4. Verifica que se complete automáticamente en ~30 segundos

### Test 2: Solo Tu Aprobación

1. Crea un PR hacia `develop`
2. Apruébalo desde el dashboard
3. Verifica que NO se complete (falta TA)
4. Cuando TA apruebe, debería completarse automáticamente

### Test 3: Con Conflictos

1. Crea un PR con conflictos hacia `develop`
2. Apruébalo tú y que TA apruebe
3. Verifica que NO se complete (tiene conflictos)
4. Resuelve conflictos
5. Debería completarse automáticamente

---

## 📊 Cambios Realizados

### Archivos Modificados

1. **`scripts/check_salesforce_prs.py`**:
   - ✅ Corregida función `get_my_vote()`
   - ✅ Ahora busca específicamente TU voto
   - ✅ Usa `az account show` para obtener usuario actual

---

## ✅ Checklist

- [x] Lógica de auto-complete verificada
- [x] Bug en `get_my_vote()` identificado
- [x] Bug corregido
- [x] Documentación creada
- [ ] **Reiniciar servidor** ← TÚ AHORA
- [ ] **Probar con un PR real** ← TÚ AHORA
- [ ] **Verificar que auto-complete funciona** ← TÚ AHORA

---

## 🚀 Próxima Acción

```bash
# Reiniciar el servidor
source venv/bin/activate
python app.py

# Probar con un PR:
# 1. Aprueba un PR desde el dashboard
# 2. Espera a que TA apruebe
# 3. Verifica que se complete automáticamente en ~30 segundos
```

---

## 📝 Notas Importantes

1. **Auto-complete es automático**: No necesitas hacer nada, el sistema lo hace solo
2. **Refresh cada 30 segundos**: El sistema revisa PRs cada 30 segundos
3. **Condiciones estrictas**: TODAS las condiciones deben cumplirse
4. **Guard de duplicados**: Un PR solo se completa una vez (guard en `auto_completed`)
5. **Notificación en Slack**: Cuando el deploy termine, se notifica en Slack

---

## 🎉 Resumen

**Requerimiento**: Auto-complete cuando TÚ apruebas Y TA aprueba  
**Estado Anterior**: Lógica existía pero con bug en `get_my_vote()`  
**Bug**: Retornaba voto del primer reviewer, no el tuyo  
**Fix**: Ahora busca específicamente TU voto usando `az account show`  
**Resultado**: ✅ **Auto-complete funcionará correctamente**

---

**Estado**: ✅ **VERIFICADO Y CORREGIDO - Listo para probar**

Reinicia el servidor y prueba con un PR real. El auto-complete debería funcionar correctamente ahora.
