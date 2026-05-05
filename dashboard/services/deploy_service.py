import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from integrations.azure import get_org_url, get_project, api_azure, check_token, get_token
from utils import retry

logger = logging.getLogger("pr_dashboard")

_releases_cache = {"data": None, "ts": 0.0}
_releases_cache_lock = threading.Lock()
_RELEASES_TTL = 30

# Lock para evitar notificaciones duplicadas de deploy
_deploy_notify_lock = threading.Lock()
_deploy_notified_memory = set()  # guard en memoria para la sesión actual


def _get_releases_cached(token):
    with _releases_cache_lock:
        if time.time() - _releases_cache["ts"] < _RELEASES_TTL and _releases_cache["data"] is not None:
            return _releases_cache["data"]
    org_name = ORG_URL.rstrip("/").split("/")[-1]
    vsrm = f"https://vsrm.dev.azure.com/{org_name}/{PROJECT}"
    releases = api_azure(f"{vsrm}/_apis/release/releases?api-version=7.1&$top=50", token).get("value", [])
    with _releases_cache_lock:
        _releases_cache["data"] = releases
        _releases_cache["ts"] = time.time()
    return releases


def get_deploy_status(pr_id, merge_commit=None, closed_date=None, target_branch=None):
    try:
        token = get_token()
        org_name = ORG_URL.rstrip("/").split("/")[-1]
        vsrm = f"https://vsrm.dev.azure.com/{org_name}/{PROJECT}"
        releases = _get_releases_cached(token)
        pr_branch = f"refs/pull/{pr_id}/merge"

        def _fetch_detail(rel):
            return api_azure(f"{vsrm}/_apis/release/releases/{rel['id']}?api-version=7.1", token)

        with ThreadPoolExecutor(max_workers=10) as ex:
            details = list(ex.map(_fetch_detail, releases))

        for detail in details:
            for art in detail.get("artifacts", []):
                ref    = art.get("definitionReference", {})
                branch = ref.get("branch", {}).get("id", "")
                commit = ref.get("sourceVersion", {}).get("id", "")
                if branch == pr_branch:
                    return _release_status(detail)
                if merge_commit and commit and commit == merge_commit:
                    return _release_status(detail)
        return "unknown", ""
    except Exception:
        return "unknown", ""


def _is_checkonly_env(env):
    """Retorna True si el environment es un artefacto/checkonly (falso positivo)."""
    name = (env.get("name") or "").lower()
    return "checkonly" in name or name.startswith("build")


def _release_status(release):
    envs = release.get("environments", [])
    if not envs:
        return "unknown", ""

    # Separar environments reales (excluir Checkonly y Build)
    real_envs = [e for e in envs if not _is_checkonly_env(e)]

    # Si no hay environments reales, usar todos (fallback)
    eval_envs = real_envs if real_envs else envs

    statuses = [e.get("status", "") for e in eval_envs]

    if any(s in ("inProgress", "queued") for s in statuses):
        return "inProgress", ""

    active_envs = [e for e in eval_envs if e.get("status", "") != "notStarted"]
    if not active_envs:
        return "inProgress", ""

    active_statuses = [e.get("status", "") for e in active_envs]
    if all(s in ("succeeded", "skipped") for s in active_statuses):
        return "succeeded", _latest_deploy_date(active_envs)

    has_success = any(s in ("succeeded", "skipped") for s in active_statuses)
    has_failure = any(s in ("rejected", "failed", "canceled") for s in active_statuses)
    if has_success and has_failure:
        success_date = _latest_deploy_date([e for e in active_envs if e.get("status") in ("succeeded", "skipped")])
        failure_date = _latest_deploy_date([e for e in active_envs if e.get("status") in ("rejected", "failed", "canceled")])
        if success_date and failure_date:
            return ("succeeded", success_date) if success_date >= failure_date else ("failed", failure_date)
        return "succeeded" if success_date else "failed", success_date or failure_date
    if has_failure:
        return "failed", _latest_deploy_date(active_envs)
    return "inProgress", ""


def _latest_deploy_date(envs):
    dates = []
    for env in envs:
        for attempt in env.get("deploySteps", []):
            d = attempt.get("lastModifiedOn") or attempt.get("queuedOn", "")
            if d:
                dates.append(d)
    return max(dates) if dates else ""


def poll_deploy_background(pr_id, merge_commit, closed_date, target_branch, author=None):
    from integrations.slack import SLACK_PR_CHANNEL, find_pr_thread, slack_api
    from integrations.state import load_state, save_state, load_blocked_authors
    from services.sheets_service import update_deploy
    from datetime import datetime, timezone

    def _run():
        if author and author.lower().strip() in [a.lower().strip() for a in load_blocked_authors()]:
            return
        for attempt in range(60):
            time.sleep(60)
            if author and author.lower().strip() in [a.lower().strip() for a in load_blocked_authors()]:
                return
            try:
                status, deploy_date_bg = get_deploy_status(pr_id, merge_commit, closed_date, target_branch)
                if status in ("succeeded", "failed"):
                    with _deploy_notify_lock:
                        if int(pr_id) in _deploy_notified_memory:
                            return  # ya notificado en esta sesión
                        _deploy_notified_memory.add(int(pr_id))
                    state = load_state()
                    deploy_notified = state.setdefault("deploy_notified", [])
                    already = int(pr_id) in [int(x) for x in deploy_notified]
                    if not already:
                        deploy_notified.append(int(pr_id))
                        save_state(state)
                    if not already and not (author and author.lower().strip() in [a.lower().strip() for a in load_blocked_authors()]):
                        text = "✅ Despliegue completado" if status == "succeeded" else "❌ Despliegue fallido"
                        thread_ts = find_pr_thread(pr_id, save_if_found=True)
                        if thread_ts:
                            try:
                                slack_api("chat.postMessage", {"channel": SLACK_PR_CHANNEL, "text": text, "thread_ts": thread_ts})
                            except Exception as se:
                                logger.error("[deploy-poll] Error Slack PR %s: %s", pr_id, se)
                        else:
                            logger.warning("[deploy-poll] PR %s: hilo no encontrado para notificar deploy", pr_id)
                    final_date = deploy_date_bg or datetime.now(timezone.utc).isoformat()
                    update_deploy(pr_id, status, final_date)
                    return
            except Exception as e:
                logger.warning("[deploy-poll] PR %s intento %d: %s", pr_id, attempt + 1, e)
        logger.warning("[deploy-poll] PR %s: timeout", pr_id)

    threading.Thread(target=_run, daemon=True).start()
