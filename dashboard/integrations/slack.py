import json
import logging
import os
import threading
import time
from urllib.request import Request, urlopen

from utils import retry

logger = logging.getLogger("pr_dashboard")

# ── Configuración dinámica por tenant ─────────────────────────────────────────

def _get_slack_config():
    """Obtiene la configuración de Slack del tenant actual."""
    from integrations.tenant_context import get_current_tenant
    
    tenant = get_current_tenant()
    if tenant:
        try:
            integration = tenant.get_integration('slack')
            if integration and integration['enabled']:
                return integration['config']
        except Exception as e:
            logger.warning(f"Error obteniendo config de Slack del tenant: {e}")
    
    # Fallback a variables de entorno (para compatibilidad)
    return {
        'bot_token': os.getenv("SLACK_TOKEN"),
        'channel': os.getenv("SLACK_PR_CHANNEL", "C080K9D6EG2")
    }


def get_slack_token():
    """Obtiene el token de Slack del tenant actual."""
    config = _get_slack_config()
    return config.get('bot_token') if config else None


def get_slack_channel():
    """Obtiene el canal de Slack del tenant actual."""
    config = _get_slack_config()
    return config.get('channel') if config else None


def is_slack_enabled():
    """Verifica si Slack está habilitado para el tenant actual."""
    from integrations.tenant_context import get_current_tenant
    
    tenant = get_current_tenant()
    if tenant:
        return tenant.has_integration('slack')
    
    # Fallback: si hay token, está habilitado
    return get_slack_token() is not None


# Para compatibilidad con código existente
SLACK_TOKEN = get_slack_token()
SLACK_PR_CHANNEL = get_slack_channel()

# Guard en memoria para evitar notificaciones duplicadas en la misma sesión
_notified_lock = threading.Lock()
_notified_memory = set()  # (pr_id, action)

TA_SLACK_IDS = {
    "gustavo alonso muciño": "U06JUHG1G9Y",
    "hugo revuelta":         "U07TQ8JNMBR",
    "gabriel alvis":         "U066X49C5NZ",
    "francisco zubizarreta": "U01LXV1UD3K",
    "luís guilherme lino":   "U023L6SJVQW",
    "luis guilherme lino":   "U023L6SJVQW",
}


def slack_api(method, payload):
    """Llama a la API de Slack usando la configuración del tenant actual."""
    # Verificar si Slack está habilitado
    if not is_slack_enabled():
        logger.debug("Slack no está habilitado para este tenant, omitiendo llamada a API")
        return {"ok": True, "skipped": True}
    
    token = get_slack_token()
    if not token:
        logger.warning("No hay token de Slack configurado")
        return {"ok": False, "error": "no_token"}
    
    def _call():
        data = json.dumps(payload).encode()
        req = Request(
            f"https://slack.com/api/{method}",
            data=data,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        with urlopen(req, timeout=5) as r:
            resp = json.loads(r.read())
        if not resp.get("ok"):
            raise RuntimeError(f"Slack API error [{method}]: {resp.get('error', 'unknown')}")
        return resp
    return retry(_call, retries=2, label=f"slack.{method}")


def find_pr_thread(pr_id, save_if_found=False):
    """Busca el thread de Slack para un PR."""
    # Verificar si Slack está habilitado
    if not is_slack_enabled():
        return None
    
    channel = get_slack_channel()
    if not channel:
        return None
    
    from integrations.state import load_state, save_state
    state = load_state()
    pr_threads = state.setdefault("pr_threads", {})
    if str(pr_id) in pr_threads:
        return pr_threads[str(pr_id)]
    result = slack_api("conversations.history", {"channel": channel, "limit": 200})
    
    # Si Slack está deshabilitado, slack_api retorna con skipped=True
    if result.get("skipped"):
        return None
    
    needle = f"pullrequest/{pr_id}"
    for msg in result.get("messages", []):
        text_blob = json.dumps(msg)
        if needle in text_blob:
            thread_ts = msg["ts"]
            if save_if_found:
                pr_threads[str(pr_id)] = thread_ts
                save_state(state)
            return thread_ts
    return None


def wait_for_pr_thread(pr_id, interval=5, max_wait=30):
    elapsed = 0
    while elapsed < max_wait:
        ts = find_pr_thread(pr_id, save_if_found=True)
        if ts:
            return ts
        time.sleep(interval)
        elapsed += interval
    logger.warning("[slack] No se encontró hilo para PR %s tras %ds", pr_id, max_wait)
    return None


def notify_pr_slack(pr_id, action, detail=None):
    # Guard: evitar duplicados para la misma acción en la misma sesión
    key = (int(pr_id), action)
    with _notified_lock:
        if key in _notified_memory:
            logger.info("[slack] Notificación duplicada ignorada PR %s acción %s", pr_id, action)
            return
        _notified_memory.add(key)

    labels = {
        "approve":  "✅ Aprobado",
        "reject":   "❌ Rechazado",
        "complete": "🚀 PR integrado — si no hay conflicto el despliegue estará en curso, te avisamos cuando termine.",
    }
    text = labels.get(action, action)
    if detail:
        text += f"\n> {detail}"

    def _send():
        try:
            elapsed = 0
            max_wait = 1800
            interval = 15
            thread_ts = None
            while elapsed < max_wait:
                thread_ts = find_pr_thread(pr_id, save_if_found=True)
                if thread_ts:
                    break
                time.sleep(interval)
                elapsed += interval
            if not thread_ts:
                logger.warning("[slack] No se pudo notificar PR %s (acción: %s): hilo no encontrado", pr_id, action)
                return
            slack_api("chat.postMessage", {"channel": SLACK_PR_CHANNEL, "text": text, "thread_ts": thread_ts})
            logger.info("[slack] Notificación enviada PR %s acción %s", pr_id, action)
        except Exception as e:
            logger.error("[slack] Error notificando PR %s (acción: %s): %s", pr_id, action, e)
            # Si falla, remover del guard para permitir reintento
            with _notified_lock:
                _notified_memory.discard(key)

    threading.Thread(target=_send, daemon=True).start()
