#!/usr/bin/env python3
import json
import logging
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone, timedelta
from functools import wraps
from pathlib import Path
from urllib.request import Request, urlopen

from flask import Flask, jsonify, render_template, request
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).parent))

from utils import validate_date, minutes_between, retry
from integrations.azure import (
    get_org_url, get_project, get_repository, check_token, get_token, invalidate_token,
    get_pr_policy_status, get_pr_approval_date, get_pr_ta_reviewers,
    list_completed_prs, complete_pr, set_pr_vote, add_pr_comment,
    normalize_ref, TokenExpiredError,
)
from integrations.slack import (
    SLACK_PR_CHANNEL, find_pr_thread, wait_for_pr_thread,
    notify_pr_slack, slack_api,
)
from integrations.state import (
    load_state, save_state,
    load_auto_approve_config, save_auto_approve_config,
    load_blocked_authors, save_blocked_authors,
    load_blocked_branches, save_blocked_branches,
)
from integrations.tenant_context import (
    get_tenant_by_api_key, set_current_tenant, get_current_tenant
)
from services.pr_service import get_prs, invalidate_prs_cache
from services.deploy_service import get_deploy_status, poll_deploy_background
from services.sheets_service import (
    SHEET_HEADERS, pr_to_row, append_pr, update_deploy, export_range,
)
from services.rules_service import (
    get_all_rules, get_branch_rules, get_custom_rules,
    update_branch_rule, create_custom_rule, update_custom_rule,
    delete_custom_rule, toggle_rule,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("pr_dashboard")

API_KEY = os.getenv("API_KEY")
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "5000"))
DEBUG = os.getenv("FLASK_DEBUG", os.getenv("DEBUG", "0")).lower() in {"1", "true", "yes", "on"}

app = Flask(__name__)


# ── Tenant Middleware ─────────────────────────────────────────────────────────

@app.before_request
def identify_tenant():
    """
    Identifica el tenant antes de cada petición HTTP.
    El tenant se identifica por la API Key en los headers.
    """
    # Obtener API Key de la petición
    api_key = _request_api_key()
    
    if api_key:
        # Buscar tenant por API Key
        tenant = get_tenant_by_api_key(api_key)
        if tenant:
            # Establecer tenant en el contexto
            set_current_tenant(tenant)
            logger.debug(f"Tenant identificado: {tenant.company_name} (ID: {tenant.id})")
        else:
            logger.warning(f"API Key no válida: {api_key[:10]}...")
    else:
        # Sin API Key, usar tenant por defecto (ID 1) para compatibilidad
        from integrations.tenant_context import get_tenant_by_id
        default_tenant = get_tenant_by_id(1)
        if default_tenant:
            set_current_tenant(default_tenant)
            logger.debug("Usando tenant por defecto (ID: 1)")


# ── Auth ──────────────────────────────────────────────────────────────────────

def _request_api_key():
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    return request.headers.get("X-API-Key") or request.args.get("api_key")


def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not API_KEY:
            logger.error("Intento de acceso a endpoint protegido sin API_KEY configurado")
            return jsonify({"ok": False, "error": "API_KEY no configurada en el servidor"}), 503
        key = _request_api_key()
        if key != API_KEY:
            return jsonify({"ok": False, "error": "No autorizado"}), 401
        return f(*args, **kwargs)
    return decorated


def require_tenant_api_key(f):
    """Decorator que requiere una API Key válida de tenant."""
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = _request_api_key()
        if not api_key:
            return jsonify({"ok": False, "error": "API Key requerida"}), 401
        
        tenant = get_tenant_by_api_key(api_key)
        if not tenant:
            return jsonify({"ok": False, "error": "API Key inválida"}), 401
        
        set_current_tenant(tenant)
        return f(*args, **kwargs)
    return decorated


# ── Helpers ───────────────────────────────────────────────────────────────────

def prs_completed_by_date(date_from, date_to):
    prs = list_completed_prs()
    return [
        {
            "id": p["pullRequestId"], "title": p["title"],
            "createdBy": p.get("createdBy", {}).get("displayName", ""),
            "target": normalize_ref(p.get("targetRefName", "")),
            "closedDate": p.get("closedDate", ""),
            "creationDate": p.get("creationDate", ""),
            "mergeCommit": p.get("lastMergeCommit", {}).get("commitId", ""),
            "url": f"{get_org_url()}/{get_project()}/_git/{get_repository()}/pullrequest/{p['pullRequestId']}",
            "hasConflicts": p.get("mergeStatus") == "conflicts",
            "policyStatus": "",
            "reviewers": p.get("reviewers", []),
            "blocked": False,
        }
        for p in prs if date_from <= p.get("closedDate", "")[:10] <= date_to
    ]


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health")
def health():
    return jsonify({"ok": True, "status": "healthy", "ts": datetime.now(timezone.utc).isoformat()})


@app.route("/api/cache/clear", methods=["POST"])
@require_api_key
def clear_cache():
    """Limpia el cache de tenants y PRs"""
    from integrations.tenant_context import clear_tenant_cache
    clear_tenant_cache()
    invalidate_prs_cache()
    return jsonify({"ok": True, "message": "Cache limpiado correctamente"})


@app.route("/api/auth/login", methods=["POST"])
@require_api_key
def auth_login():
    def _run():
        subprocess.run([
            "az", "login", "--allow-no-subscriptions",
            "--tenant", "46bb22b8-4c2c-40ff-8360-7b6334821279"
        ])
        invalidate_token()
        invalidate_prs_cache()
    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"ok": True})


@app.route("/api/prs")
def api_prs():
    try:
        return jsonify({"ok": True, "prs": get_prs()})
    except TokenExpiredError:
        return jsonify({"ok": False, "error": "TOKEN_EXPIRED"}), 401
    except Exception as e:
        logger.error("[api/prs] %s", e, exc_info=True)
        return jsonify({"ok": False, "error": "Error consultando PRs activos"}), 500


@app.route("/api/prs/completed")
def api_prs_completed():
    try:
        today = datetime.now(timezone.utc).date().isoformat()
        return jsonify({"ok": True, "prs": prs_completed_by_date(today, today)})
    except Exception as e:
        logger.error("[api/prs/completed] %s", e, exc_info=True)
        return jsonify({"ok": False, "error": "Error consultando PRs completados"}), 500


@app.route("/api/prs/completed/yesterday")
def api_prs_yesterday():
    try:
        yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
        return jsonify({"ok": True, "prs": prs_completed_by_date(yesterday, yesterday)})
    except Exception as e:
        logger.error("[api/prs/yesterday] %s", e, exc_info=True)
        return jsonify({"ok": False, "error": "Error consultando PRs de ayer"}), 500


@app.route("/api/prs/completed/range")
def api_prs_range():
    try:
        date_from = request.args.get("from", "").strip()
        date_to   = request.args.get("to", "").strip()
        if not date_from or not date_to:
            return jsonify({"ok": False, "error": "Parámetros 'from' y 'to' requeridos (YYYY-MM-DD)"}), 400
        validate_date(date_from)
        validate_date(date_to)
        if date_from > date_to:
            return jsonify({"ok": False, "error": "'from' no puede ser posterior a 'to'"}), 400
        return jsonify({"ok": True, "prs": prs_completed_by_date(date_from, date_to)})
    except ValueError as ve:
        return jsonify({"ok": False, "error": str(ve)}), 400
    except Exception as e:
        logger.error("[api/prs/range] %s", e, exc_info=True)
        return jsonify({"ok": False, "error": "Error consultando rango de PRs"}), 500


@app.route("/api/history")
def api_history():
    try:
        today = datetime.now(timezone.utc).date().isoformat()
        date_from = request.args.get("from", today).strip()
        date_to   = request.args.get("to", today).strip()
        validate_date(date_from)
        validate_date(date_to)
        prs = prs_completed_by_date(date_from, date_to)
        state = load_state()
        auto_approved_ids = set(state.get("auto_approved", []))
        blocked_authors = [a.lower().strip() for a in load_blocked_authors()]
        token = get_token()
        rows = []
        for pr in prs:
            pr_id = pr["id"]
            pr["blocked"] = (pr.get("createdBy") or "").lower().strip() in blocked_authors
            try:
                pr["policyStatus"] = get_pr_policy_status(pr_id, token)
            except Exception:
                pr["policyStatus"] = ""
            approval_date = get_pr_approval_date(pr_id, token) or pr.get("closedDate", "")
            deploy_st, deploy_date = get_deploy_status(pr_id, pr.get("mergeCommit"), pr.get("closedDate"), pr.get("target"))
            rows.append(pr_to_row(pr, deploy_status=deploy_st, deploy_date=deploy_date,
                                  approval_date=approval_date, auto_approved=pr_id in auto_approved_ids))
        return jsonify({"ok": True, "headers": SHEET_HEADERS, "rows": rows})
    except Exception as e:
        logger.error("[api/history] %s", e, exc_info=True)
        return jsonify({"ok": False, "error": "Error consultando historial"}), 500


@app.route("/api/pr/<int:pr_id>/approve", methods=["POST"])
@require_api_key
def approve(pr_id):
    try:
        result = set_pr_vote(pr_id, "approve")
        if result.returncode != 0:
            logger.error("[approve] PR %s falló: %s", pr_id, result.stderr)
            return jsonify({"ok": False, "error": "Error al aprobar el PR"}), 500
        state = load_state()
        approved_notified = state.setdefault("approved_notified", [])
        if pr_id not in approved_notified:
            notify_pr_slack(pr_id, "approve")
            approved_notified.append(pr_id)
            save_state(state)

        def _notify_ta():
            try:
                state2 = load_state()
                ta_notified = state2.setdefault("ta_notified", [])
                if pr_id not in ta_notified:
                    thread_ts = wait_for_pr_thread(pr_id, interval=5)
                    if not thread_ts:
                        return
                    token = get_token()
                    mentions = get_pr_ta_reviewers(pr_id, token)
                    text = f"{' '.join(mentions)} TA por favor revisa este PR" if mentions else "TA por favor revisa este PR"
                    slack_api("chat.postMessage", {"channel": SLACK_PR_CHANNEL, "thread_ts": thread_ts, "text": text})
                    ta_notified.append(pr_id)
                    save_state(state2)
            except Exception as e:
                logger.error("[approve] TA PR %s: %s", pr_id, e)

        threading.Thread(target=_notify_ta, daemon=True).start()
        invalidate_prs_cache()
        return jsonify({"ok": True, "ta_notified": True})
    except Exception as e:
        logger.error("[approve] PR %s: %s", pr_id, e, exc_info=True)
        return jsonify({"ok": False, "error": "Error interno al aprobar"}), 500


@app.route("/api/pr/<int:pr_id>/reject", methods=["POST"])
@require_api_key
def reject(pr_id):
    try:
        data = request.get_json(silent=True) or {}
        comment = str(data.get("comment", "PR rechazado por revisión automática."))
        if len(comment) > 2000:
            return jsonify({"ok": False, "error": "Comentario demasiado largo (máx 2000 caracteres)"}), 400
        result = set_pr_vote(pr_id, "reject")
        if result.returncode != 0:
            return jsonify({"ok": False, "error": "Error al rechazar el PR"}), 500
        add_pr_comment(pr_id, comment)
        notify_pr_slack(pr_id, "reject", comment)
        invalidate_prs_cache()
        return jsonify({"ok": True})
    except Exception as e:
        logger.error("[reject] PR %s: %s", pr_id, e, exc_info=True)
        return jsonify({"ok": False, "error": "Error interno al rechazar"}), 500


@app.route("/api/pr/<int:pr_id>/complete", methods=["POST"])
@require_api_key
def complete(pr_id):
    try:
        state = load_state()
        result = complete_pr(pr_id)
        if result.returncode != 0:
            return jsonify({"ok": False, "error": "Error al completar el PR"}), 500
        pr_data = {}
        if result.stdout.strip().startswith("{"):
            try:
                pr_data = json.loads(result.stdout)
            except json.JSONDecodeError:
                pass
        author = pr_data.get("createdBy", {}).get("displayName", "")
        merge_commit  = pr_data.get("lastMergeCommit", {}).get("commitId")
        closed_date   = pr_data.get("closedDate", "")
        target_branch = pr_data.get("targetRefName", "")
        poll_deploy_background(pr_id, merge_commit, closed_date, target_branch, author=author)
        token = get_token()
        approval_date = get_pr_approval_date(pr_id, token)
        policy_status = get_pr_policy_status(pr_id, token)
        sheet_pr = {
            "pullRequestId": pr_id,
            "title": pr_data.get("title", ""),
            "createdBy": author,
            "targetRefName": target_branch,
            "creationDate": pr_data.get("creationDate", ""),
            "closedDate": closed_date,
            "hasConflicts": pr_data.get("mergeStatus") == "conflicts",
            "policyStatus": policy_status,
        }
        state = load_state()
        append_pr(sheet_pr, auto_approved=pr_id in state.get("auto_approved", []), approval_date=approval_date)
        invalidate_prs_cache()
        return jsonify({"ok": True})
    except Exception as e:
        logger.error("[complete] PR %s: %s", pr_id, e, exc_info=True)
        return jsonify({"ok": False, "error": "Error interno al completar"}), 500


@app.route("/api/pr/<int:pr_id>/notify-deploy", methods=["POST"])
@require_api_key
def notify_deploy(pr_id):
    try:
        state = load_state()
        deploy_notified = state.setdefault("deploy_notified", [])
        already = int(pr_id) in [int(x) for x in deploy_notified]
        if not already:
            deploy_notified.append(int(pr_id))
            save_state(state)
        if already:
            return jsonify({"ok": True})
        data   = request.get_json(silent=True) or {}
        status = data.get("status", "")
        if status not in ("succeeded", "failed", "inProgress", "unknown"):
            return jsonify({"ok": False, "error": "Estado de deploy inválido"}), 400
        text = "✅ Despliegue completado" if status == "succeeded" else "❌ Despliegue fallido"
        thread_ts = find_pr_thread(pr_id, save_if_found=True)
        if not thread_ts:
            return jsonify({"ok": False, "error": f"No se encontró el hilo del PR {pr_id}"}), 404
        slack_api("chat.postMessage", {"channel": SLACK_PR_CHANNEL, "text": text, "thread_ts": thread_ts})
        return jsonify({"ok": True})
    except Exception as e:
        logger.error("[notify-deploy] PR %s: %s", pr_id, e, exc_info=True)
        return jsonify({"ok": False, "error": "Error interno al notificar deploy"}), 500


@app.route("/api/pr/<int:pr_id>/deploy-status")
def deploy_status(pr_id):
    try:
        status, _ = get_deploy_status(
            pr_id,
            request.args.get("mergeCommit", ""),
            request.args.get("closedDate", ""),
            request.args.get("target", ""),
        )
        return jsonify({"ok": True, "status": status})
    except Exception as e:
        logger.error("[deploy-status] PR %s: %s", pr_id, e, exc_info=True)
        return jsonify({"ok": True, "status": "unknown"})


@app.route("/api/pr/<int:pr_id>/request-ta-approval", methods=["POST"])
@require_api_key
def request_ta_approval(pr_id):
    try:
        state = load_state()
        ta_notified = state.setdefault("ta_notified", [])
        if pr_id in ta_notified:
            return jsonify({"ok": True, "already_notified": True})
        thread_ts = wait_for_pr_thread(pr_id)
        if not thread_ts:
            return jsonify({"ok": False, "error": "No se encontró el hilo del PR"}), 404
        time.sleep(5)
        token = get_token()
        mentions = get_pr_ta_reviewers(pr_id, token) or []
        text = f"{' '.join(mentions)} TA por favor revisa este PR" if mentions else "TA por favor revisa este PR"
        slack_api("chat.postMessage", {"channel": SLACK_PR_CHANNEL, "thread_ts": thread_ts, "text": text})
        ta_notified.append(pr_id)
        save_state(state)
        return jsonify({"ok": True})
    except Exception as e:
        logger.error("[request-ta-approval] PR %s: %s", pr_id, e, exc_info=True)
        return jsonify({"ok": False, "error": "Error interno al notificar TA"}), 500


# ── Config endpoints ──────────────────────────────────────────────────────────

@app.route("/api/config/auto-approve", methods=["GET"])
def get_auto_approve():
    return jsonify(load_auto_approve_config())


@app.route("/api/config/auto-approve", methods=["POST"])
@require_api_key
def set_auto_approve():
    try:
        data = request.get_json(silent=True) or {}
        cfg = load_auto_approve_config()
        if "enabled" in data:
            cfg["enabled"] = bool(data["enabled"])
        if "branches" in data:
            cfg["branches"] = [str(b).strip() for b in data["branches"] if str(b).strip()]
        save_auto_approve_config(cfg)
        return jsonify({"ok": True, "config": cfg})
    except Exception as e:
        logger.error("[config/auto-approve] %s", e, exc_info=True)
        return jsonify({"ok": False, "error": "Error guardando configuración"}), 500


@app.route("/api/config/blocked-authors", methods=["GET"])
def get_blocked_authors_route():
    return jsonify(load_blocked_authors())


@app.route("/api/config/blocked-authors", methods=["POST"])
@require_api_key
def set_blocked_authors_route():
    try:
        data = request.get_json(silent=True) or {}
        validated = [str(a).strip() for a in data.get("authors", []) if str(a).strip() and len(str(a)) <= 200]
        if len(validated) > 100:
            return jsonify({"ok": False, "error": "Máximo 100 autores bloqueados"}), 400
        save_blocked_authors(validated)
        return jsonify({"ok": True, "authors": validated})
    except Exception as e:
        logger.error("[config/blocked-authors] %s", e, exc_info=True)
        return jsonify({"ok": False, "error": "Error guardando autores bloqueados"}), 500


@app.route("/api/config/blocked-branches", methods=["GET"])
def get_blocked_branches_route():
    return jsonify(load_blocked_branches())


@app.route("/api/config/blocked-branches", methods=["POST"])
@require_api_key
def set_blocked_branches_route():
    try:
        data = request.get_json(silent=True) or {}
        validated = [str(b).strip() for b in data.get("branches", []) if str(b).strip() and len(str(b)) <= 200]
        if len(validated) > 100:
            return jsonify({"ok": False, "error": "Máximo 100 ramas bloqueadas"}), 400
        save_blocked_branches(validated)
        return jsonify({"ok": True, "branches": validated})
    except Exception as e:
        logger.error("[config/blocked-branches] %s", e, exc_info=True)
        return jsonify({"ok": False, "error": "Error guardando ramas bloqueadas"}), 500


@app.route("/api/branches")
def api_branches():
    """Obtiene todas las ramas gestionadas en el sistema."""
    try:
        from integrations.state import load_managed_branches
        branches = load_managed_branches()
        return jsonify({"ok": True, "branches": branches})
    except Exception as e:
        logger.error("[api/branches] %s", e, exc_info=True)
        return jsonify({"ok": False, "error": "Error cargando ramas"}), 500


@app.route("/api/branches/managed", methods=["GET"])
def get_managed_branches():
    """Obtiene información detallada de todas las ramas gestionadas."""
    try:
        from integrations.state import load_managed_branches, get_branch_info
        branches = load_managed_branches()
        
        branches_info = []
        for branch in branches:
            info = get_branch_info(branch)
            if info.get("ok"):
                branches_info.append(info["branch"])
        
        return jsonify({"ok": True, "branches": branches_info})
    except Exception as e:
        logger.error("[api/branches/managed] %s", e, exc_info=True)
        return jsonify({"ok": False, "error": "Error cargando información de ramas"}), 500


@app.route("/api/branches/managed", methods=["POST"])
@require_api_key
def add_managed_branch():
    """Agrega una nueva rama al sistema."""
    try:
        from integrations.state import add_managed_branch as add_branch
        
        data = request.get_json(silent=True) or {}
        branch_name = data.get("name", "").strip()
        
        if not branch_name:
            return jsonify({"ok": False, "error": "Nombre de rama requerido"}), 400
        
        # Validar nombre de rama
        if len(branch_name) > 200:
            return jsonify({"ok": False, "error": "Nombre de rama demasiado largo"}), 400
        
        # Configuración opcional
        branch_config = data.get("config")
        
        result = add_branch(branch_name, branch_config)
        
        if not result.get("ok"):
            return jsonify(result), 400
        
        invalidate_prs_cache()
        return jsonify(result), 201
    except Exception as e:
        logger.error("[api/branches/managed] POST %s", e, exc_info=True)
        return jsonify({"ok": False, "error": "Error agregando rama"}), 500


@app.route("/api/branches/managed/<path:branch_name>", methods=["DELETE"])
@require_api_key
def remove_managed_branch(branch_name):
    """Elimina una rama del sistema."""
    try:
        from integrations.state import remove_managed_branch as remove_branch
        
        result = remove_branch(branch_name)
        
        if not result.get("ok"):
            return jsonify(result), 404
        
        invalidate_prs_cache()
        return jsonify(result)
    except Exception as e:
        logger.error("[api/branches/managed] DELETE %s: %s", branch_name, e, exc_info=True)
        return jsonify({"ok": False, "error": "Error eliminando rama"}), 500


@app.route("/api/branches/managed/<path:branch_name>", methods=["GET"])
def get_branch_info_api(branch_name):
    """Obtiene información detallada de una rama."""
    try:
        from integrations.state import get_branch_info
        
        result = get_branch_info(branch_name)
        
        if not result.get("ok"):
            return jsonify(result), 404
        
        return jsonify(result)
    except Exception as e:
        logger.error("[api/branches/managed] GET %s: %s", branch_name, e, exc_info=True)
        return jsonify({"ok": False, "error": "Error obteniendo información de rama"}), 500


@app.route("/api/config/pr-validation-rules", methods=["GET"])
def get_pr_validation_rules_route():
    """Obtiene las reglas de validación de PR configurables."""
    try:
        from integrations.state import load_pr_validation_rules
        rules = load_pr_validation_rules()
        return jsonify({"ok": True, "rules": rules})
    except Exception as e:
        logger.error("[config/pr-validation-rules] GET %s", e, exc_info=True)
        return jsonify({"ok": False, "error": "Error cargando reglas"}), 500


@app.route("/api/config/pr-validation-rules", methods=["POST"])
@require_api_key
def set_pr_validation_rules_route():
    """Guarda las reglas de validación de PR."""
    try:
        from integrations.state import save_pr_validation_rules
        data = request.get_json(silent=True) or {}
        rules = data.get("rules", {})
        
        # Validación básica
        if not isinstance(rules, dict):
            return jsonify({"ok": False, "error": "Formato de reglas inválido"}), 400
        
        save_pr_validation_rules(rules)
        invalidate_prs_cache()  # Invalidar cache para refrescar con nuevas reglas
        return jsonify({"ok": True, "rules": rules})
    except Exception as e:
        logger.error("[config/pr-validation-rules] POST %s", e, exc_info=True)
        return jsonify({"ok": False, "error": "Error guardando reglas"}), 500


# ── Validation Rules Management (Legacy - mantener para compatibilidad) ──────

@app.route("/api/validation-rules", methods=["GET"])
def get_all_validation_rules():
    """Obtiene todas las reglas de validación (branch + custom)."""
    try:
        from integrations.state import get_all_validation_rules
        rules = get_all_validation_rules()
        return jsonify({"ok": True, "rules": rules})
    except Exception as e:
        logger.error("[validation-rules] GET %s", e, exc_info=True)
        return jsonify({"ok": False, "error": "Error cargando reglas"}), 500


@app.route("/api/validation-rules", methods=["POST"])
@require_api_key
def save_all_validation_rules_route():
    """Guarda todas las reglas de validación."""
    try:
        from integrations.state import save_all_validation_rules
        data = request.get_json(silent=True) or {}
        branch_rules = data.get("branch_rules")
        custom_rules = data.get("custom_rules")
        
        save_all_validation_rules(branch_rules, custom_rules)
        invalidate_prs_cache()
        
        from integrations.state import get_all_validation_rules
        return jsonify({"ok": True, "rules": get_all_validation_rules()})
    except Exception as e:
        logger.error("[validation-rules] POST %s", e, exc_info=True)
        return jsonify({"ok": False, "error": "Error guardando reglas"}), 500


@app.route("/api/validation-rules/custom/<rule_id>", methods=["PUT"])
@require_api_key
def update_validation_custom_rule(rule_id):
    """Actualiza una regla personalizada (legacy)."""
    try:
        from integrations.state import load_custom_rules, save_custom_rules
        data = request.get_json(silent=True) or {}
        
        rules = load_custom_rules()
        if rule_id not in rules:
            return jsonify({"ok": False, "error": "Regla no encontrada"}), 404
        
        for key in ["name", "description", "enabled", "type", "pattern", 
                    "validation_type", "validation_pattern", "error_message", "severity"]:
            if key in data:
                rules[rule_id][key] = data[key]
        
        save_custom_rules(rules)
        invalidate_prs_cache()
        return jsonify({"ok": True, "rule": rules[rule_id]})
    except Exception as e:
        logger.error("[validation-rules/custom] PUT %s: %s", rule_id, e, exc_info=True)
        return jsonify({"ok": False, "error": "Error actualizando regla"}), 500


@app.route("/api/validation-rules/custom", methods=["POST"])
@require_api_key
def create_validation_custom_rule():
    """Crea una nueva regla personalizada (legacy)."""
    try:
        from integrations.state import load_custom_rules, save_custom_rules
        data = request.get_json(silent=True) or {}
        
        rule_id = data.get("id", "").strip()
        if not rule_id:
            return jsonify({"ok": False, "error": "ID de regla requerido"}), 400
        
        rules = load_custom_rules()
        if rule_id in rules:
            return jsonify({"ok": False, "error": "Regla ya existe"}), 409
        
        rules[rule_id] = {
            "name": data.get("name", "Nueva Regla"),
            "description": data.get("description", ""),
            "enabled": data.get("enabled", True),
            "type": data.get("type", "file_pattern"),
            "pattern": data.get("pattern", ".*"),
            "validation_type": data.get("validation_type", "exists"),
            "validation_pattern": data.get("validation_pattern", ""),
            "error_message": data.get("error_message", "Validación fallida"),
            "severity": data.get("severity", "warning")
        }
        
        save_custom_rules(rules)
        invalidate_prs_cache()
        return jsonify({"ok": True, "rule": rules[rule_id]})
    except Exception as e:
        logger.error("[validation-rules/custom] POST %s", e, exc_info=True)
        return jsonify({"ok": False, "error": "Error creando regla"}), 500


@app.route("/api/validation-rules/custom/<rule_id>", methods=["DELETE"])
@require_api_key
def delete_validation_custom_rule(rule_id):
    """Elimina una regla personalizada (legacy)."""
    try:
        from integrations.state import load_custom_rules, save_custom_rules
        
        rules = load_custom_rules()
        if rule_id not in rules:
            return jsonify({"ok": False, "error": "Regla no encontrada"}), 404
        
        del rules[rule_id]
        save_custom_rules(rules)
        invalidate_prs_cache()
        return jsonify({"ok": True})
    except Exception as e:
        logger.error("[validation-rules/custom] DELETE %s: %s", rule_id, e, exc_info=True)
        return jsonify({"ok": False, "error": "Error eliminando regla"}), 500


# ── Rules Management Module ──────────────────────────────────────────────────

@app.route("/api/rules", methods=["GET"])
def get_rules():
    """Obtiene todas las reglas (branch + custom)."""
    try:
        rules = get_all_rules()
        return jsonify({"ok": True, "rules": rules})
    except Exception as e:
        logger.error("[rules] GET %s", e, exc_info=True)
        return jsonify({"ok": False, "error": "Error cargando reglas"}), 500


@app.route("/api/rules", methods=["POST"])
@require_api_key
def save_all_rules_route():
    """Guarda todas las reglas (branch + custom)."""
    try:
        data = request.get_json(silent=True) or {}
        branch_rules = data.get("branch_rules")
        custom_rules = data.get("custom_rules")
        
        from integrations.state import save_all_validation_rules
        save_all_validation_rules(branch_rules, custom_rules)
        invalidate_prs_cache()
        
        return jsonify({"ok": True, "rules": get_all_rules()})
    except Exception as e:
        logger.error("[rules] POST %s", e, exc_info=True)
        return jsonify({"ok": False, "error": "Error guardando reglas"}), 500


@app.route("/api/rules/branch", methods=["GET"])
def get_branch_rules_route():
    """Obtiene solo las reglas de branch."""
    try:
        rules = get_branch_rules()
        return jsonify({"ok": True, "rules": rules})
    except Exception as e:
        logger.error("[rules/branch] GET %s", e, exc_info=True)
        return jsonify({"ok": False, "error": "Error cargando reglas de branch"}), 500


@app.route("/api/rules/custom", methods=["GET"])
def get_custom_rules_route():
    """Obtiene solo las reglas personalizadas."""
    try:
        rules = get_custom_rules()
        return jsonify({"ok": True, "rules": rules})
    except Exception as e:
        logger.error("[rules/custom] GET %s", e, exc_info=True)
        return jsonify({"ok": False, "error": "Error cargando reglas personalizadas"}), 500


@app.route("/api/rules/branch/<branch_name>", methods=["PUT"])
@require_api_key
def update_branch_rule_api(branch_name):
    """Actualiza una regla de branch."""
    try:
        data = request.get_json(silent=True) or {}
        
        # Obtener información del usuario
        changed_by = request.headers.get("X-User-Name", "api_user")
        ip_address = request.remote_addr
        
        result = update_branch_rule(branch_name, data, changed_by, ip_address)
        
        if not result.get("ok"):
            return jsonify(result), 400
        
        invalidate_prs_cache()
        return jsonify(result)
    except Exception as e:
        logger.error("[rules/branch] PUT %s: %s", branch_name, e, exc_info=True)
        return jsonify({"ok": False, "error": "Error actualizando regla"}), 500


@app.route("/api/rules/custom", methods=["POST"])
@require_api_key
def create_custom_rule_api():
    """Crea una nueva regla personalizada."""
    try:
        data = request.get_json(silent=True) or {}
        rule_id = data.get("id", "").strip()
        
        if not rule_id:
            return jsonify({"ok": False, "error": "ID de regla requerido"}), 400
        
        # Obtener información del usuario
        changed_by = request.headers.get("X-User-Name", "api_user")
        ip_address = request.remote_addr
        
        result = create_custom_rule(rule_id, data, changed_by, ip_address)
        
        if not result.get("ok"):
            return jsonify(result), 400
        
        invalidate_prs_cache()
        return jsonify(result), 201
    except Exception as e:
        logger.error("[rules/custom] POST %s", e, exc_info=True)
        return jsonify({"ok": False, "error": "Error creando regla"}), 500


@app.route("/api/rules/custom/<rule_id>", methods=["PUT"])
@require_api_key
def update_custom_rule_api(rule_id):
    """Actualiza una regla personalizada."""
    try:
        data = request.get_json(silent=True) or {}
        
        # Obtener información del usuario
        changed_by = request.headers.get("X-User-Name", "api_user")
        ip_address = request.remote_addr
        
        result = update_custom_rule(rule_id, data, changed_by, ip_address)
        
        if not result.get("ok"):
            return jsonify(result), 400
        
        invalidate_prs_cache()
        return jsonify(result)
    except Exception as e:
        logger.error("[rules/custom] PUT %s: %s", rule_id, e, exc_info=True)
        return jsonify({"ok": False, "error": "Error actualizando regla"}), 500


@app.route("/api/rules/custom/<rule_id>", methods=["DELETE"])
@require_api_key
def delete_custom_rule_api(rule_id):
    """Elimina una regla personalizada."""
    try:
        # Obtener información del usuario
        changed_by = request.headers.get("X-User-Name", "api_user")
        ip_address = request.remote_addr
        
        result = delete_custom_rule(rule_id, changed_by, ip_address)
        
        if not result.get("ok"):
            return jsonify(result), 404
        
        invalidate_prs_cache()
        return jsonify(result)
    except Exception as e:
        logger.error("[rules/custom] DELETE %s: %s", rule_id, e, exc_info=True)
        return jsonify({"ok": False, "error": "Error eliminando regla"}), 500


@app.route("/api/rules/<rule_type>/<rule_id>/toggle", methods=["POST"])
@require_api_key
def toggle_rule_api(rule_type, rule_id):
    """Activa/desactiva una regla."""
    try:
        # Obtener información del usuario
        changed_by = request.headers.get("X-User-Name", "api_user")
        ip_address = request.remote_addr
        
        result = toggle_rule(rule_type, rule_id, changed_by, ip_address)
        
        if not result.get("ok"):
            return jsonify(result), 400
        
        invalidate_prs_cache()
        return jsonify(result)
    except Exception as e:
        logger.error("[rules] toggle %s/%s: %s", rule_type, rule_id, e, exc_info=True)
        return jsonify({"ok": False, "error": "Error toggling regla"}), 500


# ── Rule History Endpoints ────────────────────────────────────────────────────

@app.route("/api/rules/history", methods=["GET"])
@require_api_key
def get_rule_history_api():
    """Obtiene el historial de cambios en reglas."""
    try:
        from integrations.state import get_rule_history
        
        rule_id = request.args.get("rule_id")
        rule_type = request.args.get("rule_type")
        limit = int(request.args.get("limit", 100))
        
        history = get_rule_history(rule_id, rule_type, limit)
        return jsonify({"ok": True, "history": history})
    except Exception as e:
        logger.error("[rules/history] GET %s", e, exc_info=True)
        return jsonify({"ok": False, "error": "Error obteniendo historial"}), 500


@app.route("/api/rules/history/stats", methods=["GET"])
@require_api_key
def get_rule_history_stats_api():
    """Obtiene estadísticas del historial de cambios."""
    try:
        from integrations.state import get_rule_history_stats
        
        stats = get_rule_history_stats()
        return jsonify({"ok": True, "stats": stats})
    except Exception as e:
        logger.error("[rules/history/stats] GET %s", e, exc_info=True)
        return jsonify({"ok": False, "error": "Error obteniendo estadísticas"}), 500


@app.route("/api/rules/history/<int:history_id>/rollback", methods=["POST"])
@require_api_key
def rollback_rule_change_api(history_id):
    """Revierte un cambio en una regla."""
    try:
        from integrations.state import rollback_rule_change
        
        result = rollback_rule_change(history_id)
        
        if not result.get("ok"):
            return jsonify(result), 400
        
        invalidate_prs_cache()
        return jsonify(result)
    except Exception as e:
        logger.error("[rules/history/rollback] POST %s: %s", history_id, e, exc_info=True)
        return jsonify({"ok": False, "error": "Error revirtiendo cambio"}), 500


@app.route("/api/branch/create", methods=["POST"])
@require_api_key
def create_branch():
    try:
        data = request.get_json(silent=True) or {}
        branch_name = str(data.get("name", "")).strip()
        base_branch = str(data.get("base", "develop")).strip()
        if not branch_name:
            return jsonify({"ok": False, "error": "Nombre de rama requerido"}), 400
        from integrations.azure import api_azure
        token = get_token()
        url = f"{get_org_url()}/{get_project()}/_apis/git/repositories/{get_repository()}/refs?filter=heads/{base_branch}&api-version=7.1"
        ref_data = api_azure(url, token)
        object_id = ref_data["value"][0]["objectId"]
        result = subprocess.run([
            "az", "repos", "ref", "create",
            "--name", f"refs/heads/{branch_name}",
            "--object-id", object_id,
            "--repository", get_repository(),
            "--org", get_org_url(), "--project", get_project(), "-o", "json"
        ], capture_output=True, text=True)
        if result.returncode != 0:
            return jsonify({"ok": False, "error": result.stderr or result.stdout}), 500
        return jsonify({"ok": True, "branch": branch_name})
    except Exception as e:
        logger.error("[branch/create] %s", e, exc_info=True)
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/stats")
def api_stats():
    try:
        today = datetime.now(timezone.utc).date().isoformat()
        yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
        active_prs = get_prs()
        completed_today = prs_completed_by_date(today, today)
        completed_yesterday = prs_completed_by_date(yesterday, yesterday)
        review_times = [
            t for pr in completed_today
            if isinstance(t := minutes_between(pr.get("creationDate", ""), pr.get("closedDate", "")), (int, float)) and t > 0
        ]
        state = load_state()
        auto_approved_ids = set(state.get("auto_approved", []))
        completed_count = len(completed_today)
        auto_rate = round(sum(1 for pr in completed_today if pr["id"] in auto_approved_ids) / completed_count * 100) if completed_count else 0
        return jsonify({
            "ok": True,
            "stats": {
                "active": len(active_prs),
                "completed_today": completed_count,
                "completed_yesterday": len(completed_yesterday),
                "trend": completed_count - len(completed_yesterday),
                "conflicts": sum(1 for p in active_prs if p.get("hasConflicts")),
                "avg_review_min": round(sum(review_times) / len(review_times)) if review_times else 0,
                "auto_rate": auto_rate,
                "pending_approval": sum(1 for p in active_prs if p.get("myVote") != "approved"),
                "ready_to_complete": sum(1 for p in active_prs if p.get("canComplete") and p.get("myVote") == "approved"),
            }
        })
    except TokenExpiredError:
        return jsonify({"ok": False, "error": "TOKEN_EXPIRED"}), 401
    except Exception as e:
        logger.error("[api/stats] %s", e, exc_info=True)
        return jsonify({"ok": False, "error": "Error calculando estadísticas"}), 500


@app.route("/api/prs/export-sheets", methods=["POST"])
@require_api_key
def export_sheets():
    try:
        data = request.get_json(silent=True) or {}
        today = datetime.now(timezone.utc).date().isoformat()
        date_from = str(data.get("from", today)).strip()
        date_to   = str(data.get("to", today)).strip()
        validate_date(date_from)
        validate_date(date_to)
        prs = prs_completed_by_date(date_from, date_to)
        state = load_state()
        token = get_token()
        count = export_range(
            prs,
            auto_approved_ids=set(state.get("auto_approved", [])),
            blocked_authors=[a.lower().strip() for a in load_blocked_authors()],
            token=token,
            get_policy_fn=get_pr_policy_status,
            get_approval_fn=get_pr_approval_date,
            get_deploy_fn=get_deploy_status,
        )
        logger.info("[export-sheets] %s filas exportadas (%s → %s)", count, date_from, date_to)
        return jsonify({"ok": True, "rows": count})
    except ValueError as ve:
        return jsonify({"ok": False, "error": str(ve)}), 400
    except Exception as e:
        logger.error("[export-sheets] %s", e, exc_info=True)
        return jsonify({"ok": False, "error": "Error exportando a Sheets"}), 500


# ── Tenant Management API ────────────────────────────────────────────────────

@app.route("/api/tenants", methods=["GET"])
@require_tenant_api_key
def list_tenants():
    """Lista todos los tenants."""
    try:
        import sqlite3
        from pathlib import Path
        
        db_path = Path(__file__).parent.parent / "memoria" / "state.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        rows = cursor.execute("""
            SELECT t.*, 
                   ac.org_url, ac.project, ac.repository,
                   COUNT(CASE WHEN ti.enabled = 1 THEN 1 END) as active_integrations
            FROM tenants t
            LEFT JOIN tenant_azure_config ac ON t.id = ac.tenant_id
            LEFT JOIN tenant_integrations ti ON t.id = ti.tenant_id
            WHERE t.status = 'active'
            GROUP BY t.id
            ORDER BY t.created_at DESC
        """).fetchall()
        
        conn.close()
        
        tenants = []
        for row in rows:
            tenants.append({
                "id": row["id"],
                "subdomain": row["subdomain"],
                "company_name": row["company_name"],
                "api_key": row["api_key"],
                "plan": row["plan"],
                "status": row["status"],
                "created_at": row["created_at"],
                "azure_config": {
                    "org_url": row["org_url"],
                    "project": row["project"],
                    "repository": row["repository"]
                } if row["org_url"] else None,
                "active_integrations": row["active_integrations"] or 0
            })
        
        return jsonify({"ok": True, "tenants": tenants})
    except Exception as e:
        logger.error("[tenants] GET %s", e, exc_info=True)
        return jsonify({"ok": False, "error": "Error cargando tenants"}), 500


@app.route("/api/tenants", methods=["POST"])
@require_api_key
def create_tenant():
    """Crea un nuevo tenant."""
    try:
        import sqlite3
        import secrets
        from pathlib import Path
        
        data = request.get_json(silent=True) or {}
        
        # Validar datos requeridos
        required_fields = ["subdomain", "company_name", "plan"]
        for field in required_fields:
            if not data.get(field, "").strip():
                return jsonify({"ok": False, "error": f"Campo {field} es requerido"}), 400
        
        subdomain = data["subdomain"].strip().lower()
        company_name = data["company_name"].strip()
        plan = data["plan"].strip()
        
        # Validar plan
        if plan not in ["basic", "pro", "enterprise"]:
            return jsonify({"ok": False, "error": "Plan debe ser basic, pro o enterprise"}), 400
        
        # Generar API Key única
        api_key = f"prm_{secrets.token_urlsafe(32)}"
        
        db_path = Path(__file__).parent.parent / "memoria" / "state.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        try:
            # Crear tenant
            cursor.execute("""
                INSERT INTO tenants (subdomain, company_name, api_key, plan, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'active', datetime('now'), datetime('now'))
            """, (subdomain, company_name, api_key, plan))
            
            tenant_id = cursor.lastrowid
            
            # Configurar Azure DevOps si se proporciona
            azure_config = data.get("azure_config", {})
            if azure_config.get("org_url") and azure_config.get("project"):
                cursor.execute("""
                    INSERT INTO tenant_azure_config (tenant_id, org_url, project, repository, pat_token)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    tenant_id,
                    azure_config["org_url"],
                    azure_config["project"],
                    azure_config.get("repository", azure_config["project"]),
                    azure_config.get("pat_token", "")
                ))
            
            # Configurar integraciones si se proporcionan
            integrations = data.get("integrations", {})
            for integration_type, config in integrations.items():
                if integration_type in ["slack", "sheets"] and config.get("enabled"):
                    cursor.execute("""
                        INSERT INTO tenant_integrations (tenant_id, integration_type, enabled, config)
                        VALUES (?, ?, ?, ?)
                    """, (tenant_id, integration_type, 1, json.dumps(config.get("config", {}))))
            
            # Configuración básica del tenant
            cursor.execute("""
                INSERT INTO tenant_settings (tenant_id, language, timezone, blocked_authors, blocked_branches)
                VALUES (?, ?, ?, ?, ?)
            """, (tenant_id, "es", "America/Mexico_City", "[]", "[]"))
            
            conn.commit()
            
            return jsonify({
                "ok": True,
                "tenant": {
                    "id": tenant_id,
                    "subdomain": subdomain,
                    "company_name": company_name,
                    "api_key": api_key,
                    "plan": plan,
                    "status": "active"
                }
            })
            
        except sqlite3.IntegrityError as e:
            conn.rollback()
            if "subdomain" in str(e):
                return jsonify({"ok": False, "error": "El subdominio ya existe"}), 409
            elif "api_key" in str(e):
                return jsonify({"ok": False, "error": "Error generando API Key"}), 500
            else:
                return jsonify({"ok": False, "error": "Error de integridad de datos"}), 409
        finally:
            conn.close()
            
    except Exception as e:
        logger.error("[tenants] POST %s", e, exc_info=True)
        return jsonify({"ok": False, "error": "Error creando tenant"}), 500


@app.route("/api/tenants/<int:tenant_id>", methods=["PUT"])
@require_api_key
def update_tenant(tenant_id):
    """Actualiza un tenant."""
    try:
        import sqlite3
        from pathlib import Path
        
        data = request.get_json(silent=True) or {}
        
        db_path = Path(__file__).parent.parent / "memoria" / "state.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        try:
            # Actualizar tenant básico
            if any(key in data for key in ["company_name", "plan", "status"]):
                updates = []
                params = []
                
                if "company_name" in data:
                    updates.append("company_name = ?")
                    params.append(data["company_name"].strip())
                
                if "plan" in data and data["plan"] in ["basic", "pro", "enterprise"]:
                    updates.append("plan = ?")
                    params.append(data["plan"])
                
                if "status" in data and data["status"] in ["active", "inactive"]:
                    updates.append("status = ?")
                    params.append(data["status"])
                
                if updates:
                    updates.append("updated_at = datetime('now')")
                    params.append(tenant_id)
                    
                    cursor.execute(f"""
                        UPDATE tenants SET {', '.join(updates)}
                        WHERE id = ?
                    """, params)
            
            # Actualizar configuración de Azure DevOps
            azure_config = data.get("azure_config")
            if azure_config:
                cursor.execute("""
                    INSERT OR REPLACE INTO tenant_azure_config 
                    (tenant_id, org_url, project, repository, pat_token)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    tenant_id,
                    azure_config.get("org_url", ""),
                    azure_config.get("project", ""),
                    azure_config.get("repository", ""),
                    azure_config.get("pat_token", "")
                ))
            
            # Actualizar integraciones
            integrations = data.get("integrations", {})
            for integration_type, config in integrations.items():
                if integration_type in ["slack", "sheets"]:
                    cursor.execute("""
                        INSERT OR REPLACE INTO tenant_integrations 
                        (tenant_id, integration_type, enabled, config)
                        VALUES (?, ?, ?, ?)
                    """, (
                        tenant_id,
                        integration_type,
                        1 if config.get("enabled") else 0,
                        json.dumps(config.get("config", {}))
                    ))
            
            conn.commit()
            return jsonify({"ok": True})
            
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
            
    except Exception as e:
        logger.error("[tenants] PUT %d: %s", tenant_id, e, exc_info=True)
        return jsonify({"ok": False, "error": "Error actualizando tenant"}), 500


@app.route("/api/tenants/<int:tenant_id>", methods=["DELETE"])
@require_api_key
def delete_tenant(tenant_id):
    """Elimina un tenant (soft delete)."""
    try:
        import sqlite3
        from pathlib import Path
        
        db_path = Path(__file__).parent.parent / "memoria" / "state.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE tenants SET status = 'inactive', updated_at = datetime('now')
            WHERE id = ?
        """, (tenant_id,))
        
        conn.commit()
        conn.close()
        
        return jsonify({"ok": True})
        
    except Exception as e:
        logger.error("[tenants] DELETE %d: %s", tenant_id, e, exc_info=True)
        return jsonify({"ok": False, "error": "Error eliminando tenant"}), 500


@app.route("/api/tenants/<int:tenant_id>/regenerate-key", methods=["POST"])
@require_api_key
def regenerate_tenant_key(tenant_id):
    """Regenera la API Key de un tenant."""
    try:
        import sqlite3
        import secrets
        from pathlib import Path
        
        # Generar nueva API Key
        new_api_key = f"prm_{secrets.token_urlsafe(32)}"
        
        db_path = Path(__file__).parent.parent / "memoria" / "state.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE tenants SET api_key = ?, updated_at = datetime('now')
            WHERE id = ?
        """, (new_api_key, tenant_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({"ok": True, "api_key": new_api_key})
        
    except Exception as e:
        logger.error("[tenants] regenerate-key %d: %s", tenant_id, e, exc_info=True)
        return jsonify({"ok": False, "error": "Error regenerando API Key"}), 500


# ── Git fetch loop ────────────────────────────────────────────────────────────

LOCAL_REPO = Path("/home/zen6/cc/SalesForce")


def _git_fetch_loop():
    while True:
        try:
            tok = subprocess.run(
                ["az", "account", "get-access-token",
                 "--resource", "499b84ac-1321-427f-aa17-267ca6975798", "-o", "json"],
                capture_output=True, text=True, timeout=15,
            )
            if tok.returncode == 0:
                access_token = json.loads(tok.stdout).get("accessToken", "")
                cred_path = Path("/tmp/_git_cred_helper.sh")
                cred_path.write_text(f"#!/bin/sh\necho username=x-access-token\necho password={access_token}\n")
                cred_path.chmod(0o700)
                subprocess.run(
                    ["git", "-C", str(LOCAL_REPO), "-c", f"credential.helper={cred_path}", "fetch", "origin", "--prune"],
                    capture_output=True, timeout=30,
                    env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
                )
        except Exception:
            pass
        time.sleep(300)


if __name__ == "__main__":
    if not API_KEY:
        logger.error("API_KEY es obligatoria para arrancar el dashboard de forma segura")
        sys.exit(1)
    threading.Thread(target=_git_fetch_loop, daemon=True).start()
    app.run(host=HOST, debug=DEBUG, port=PORT, threaded=True)
