#!/usr/bin/env python3
import json
import logging
import os
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen
from flask import Flask, jsonify, render_template, request, abort
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv(Path(__file__).parent.parent / ".env")

# Google Sheets
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# ── Logging estructurado ──────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("pr_dashboard")

# ── Lock global para estado compartido ───────────────────────────────────────
_state_lock = threading.Lock()
_auto_approve_lock = threading.Lock()

# ── Configuración desde variables de entorno ──────────────────────────────────
SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "1jsYHmGm-2eN5986bgN5jlPO86guNfWmnf980H4TsdO0")
CREDS_PATH = Path(os.getenv("GOOGLE_CREDS_PATH", "../memoria/service-account-key.json"))
if not CREDS_PATH.is_absolute():
    CREDS_PATH = Path(__file__).parent.parent / CREDS_PATH

SHEET_HEADERS = [
    "PR ID", "Título", "Autor", "Branch destino",
    "Fecha creación", "Fecha aprobación", "Fecha completado", "Fecha despliegue",
    "Tiempo revisión (min)", "Tiempo merge (min)", "Tiempo despliegue (min)", "Tiempo total (min)",
    "Tenía conflictos", "Policy status", "Resultado despliegue", "Auto-aprobado", "Rechazado", "Bloqueado",
]

def _sheets_service():
    creds = Credentials.from_service_account_file(
        str(CREDS_PATH),
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    return build("sheets", "v4", credentials=creds, cache_discovery=False)

def _minutes_between(a, b):
    if not a or not b:
        return ""
    from datetime import datetime, timezone
    def parse(s):
        s = s.rstrip("Z")
        if "+" in s:
            s = s[:s.index("+")]
        return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
    try:
        return round((parse(b) - parse(a)).total_seconds() / 60)
    except Exception:
        return ""

def _pr_to_row(pr, deploy_status="", deploy_date="", approval_date="", auto_approved=False):
    created   = pr.get("creationDate", "") or pr.get("closedDate", "")
    completed = pr.get("closedDate", "")
    t_review  = _minutes_between(created, approval_date)
    t_merge   = _minutes_between(approval_date, completed)
    t_deploy  = _minutes_between(completed, deploy_date)
    t_total   = _minutes_between(created, deploy_date) if deploy_date else _minutes_between(created, completed)
    return [
        pr.get("id") or pr.get("pullRequestId", ""),
        pr.get("title", ""),
        pr.get("createdBy", ""),
        pr.get("target", "") or pr.get("targetRefName", ""),
        created[:16].replace("T", " "),
        approval_date[:16].replace("T", " ") if approval_date else "",
        completed[:16].replace("T", " "),
        deploy_date[:16].replace("T", " ") if deploy_date else "",
        t_review, t_merge, t_deploy, t_total,
        "Sí" if pr.get("hasConflicts") else "No",
        pr.get("policyStatus", ""),
        deploy_status,
        "Sí" if auto_approved else "No",
        "Sí" if pr.get("myVote") == "rejected" else "No",
        "Sí" if pr.get("blocked") else "No",
    ]

def _sheet_ensure_headers(sheet):
    """Escribe headers si la hoja está vacía."""
    result = sheet.values().get(spreadsheetId=SHEET_ID, range="Hoja 1!A1:A1").execute()
    if not result.get("values"):
        sheet.values().update(
            spreadsheetId=SHEET_ID, range="Hoja 1!A1",
            valueInputOption="RAW", body={"values": [SHEET_HEADERS]},
        ).execute()

def _sheet_find_row(sheet, pr_id):
    """Retorna el número de fila (1-based) donde está el PR, o None."""
    result = sheet.values().get(spreadsheetId=SHEET_ID, range="Hoja 1!A:A").execute()
    for i, row in enumerate(result.get("values", []), start=1):
        if row and str(row[0]) == str(pr_id):
            return i
    return None

def _sheet_append_pr(pr_data, auto_approved=False, approval_date=""):
    """Agrega una fila al Sheet cuando un PR se completa. No bloquea."""
    def _run():
        try:
            def _do():
                svc = _sheets_service()
                sheet = svc.spreadsheets()
                _sheet_ensure_headers(sheet)
                pr_id = pr_data.get("pullRequestId") or pr_data.get("id")
                if _sheet_find_row(sheet, pr_id):
                    logger.info("[sheets] PR %s ya existe en la hoja, omitiendo", pr_id)
                    return
                row = _pr_to_row(pr_data, auto_approved=auto_approved, approval_date=approval_date)
                sheet.values().append(
                    spreadsheetId=SHEET_ID, range="Hoja 1!A1",
                    valueInputOption="RAW", insertDataOption="INSERT_ROWS",
                    body={"values": [row]},
                ).execute()
                logger.info("[sheets] PR %s registrado correctamente", pr_id)
            _retry(_do, retries=2, label="sheets.append")
        except Exception as e:
            logger.error("[sheets] append error definitivo para PR %s: %s",
                         pr_data.get("pullRequestId") or pr_data.get("id"), e)
    threading.Thread(target=_run, daemon=True).start()

def _sheet_update_deploy(pr_id, deploy_status, deploy_date=""):
    """Actualiza deploy result, fecha deploy y recalcula tiempos en la fila del PR."""
    def _run():
        try:
            def _do():
                svc = _sheets_service()
                sheet = svc.spreadsheets()
                row_num = _sheet_find_row(sheet, pr_id)
                if not row_num:
                    logger.warning("[sheets] PR %s no encontrado para actualizar deploy", pr_id)
                    return
                row_data = sheet.values().get(
                    spreadsheetId=SHEET_ID, range=f"Hoja 1!A{row_num}:R{row_num}"
                ).execute().get("values", [[]])[0]
                created   = row_data[4] if len(row_data) > 4 else ""
                approval  = row_data[5] if len(row_data) > 5 else ""
                completed = row_data[6] if len(row_data) > 6 else ""
                deploy_str = deploy_date[:16].replace("T", " ") if deploy_date else ""
                t_review = _minutes_between(created, approval)
                t_merge  = _minutes_between(approval, completed)
                t_deploy = _minutes_between(completed, deploy_str)
                t_total  = _minutes_between(created, deploy_str) if deploy_str else _minutes_between(created, completed)
                updates = [
                    (f"Hoja 1!H{row_num}", [[deploy_str]]),
                    (f"Hoja 1!I{row_num}", [[t_review]]),
                    (f"Hoja 1!J{row_num}", [[t_merge]]),
                    (f"Hoja 1!K{row_num}", [[t_deploy]]),
                    (f"Hoja 1!L{row_num}", [[t_total]]),
                    (f"Hoja 1!O{row_num}", [[deploy_status]]),
                ]
                for rng, vals in updates:
                    sheet.values().update(
                        spreadsheetId=SHEET_ID, range=rng,
                        valueInputOption="RAW", body={"values": vals},
                    ).execute()
                logger.info("[sheets] Deploy de PR %s actualizado: %s", pr_id, deploy_status)
            _retry(_do, retries=2, label="sheets.update_deploy")
        except Exception as e:
            logger.error("[sheets] update deploy error definitivo para PR %s: %s", pr_id, e)
    threading.Thread(target=_run, daemon=True).start()

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from check_salesforce_prs import (
    classify, fetch_changes, get_token, normalize_ref,
    load_state as _load_state_raw, save_state as _save_state_raw, get_my_vote
)

def load_state():
    with _state_lock:
        return _load_state_raw()

def save_state(state):
    with _state_lock:
        _save_state_raw(state)

ORG = os.getenv("AZURE_ORG", "OrgClaroColombia")
ORG_URL = f"https://dev.azure.com/{ORG}"
PROJECT = os.getenv("AZURE_PROJECT", "SalesForce")
REPOSITORY = os.getenv("AZURE_REPOSITORY", "SalesForce")
SLACK_PR_CHANNEL = os.getenv("SLACK_PR_CHANNEL", "C080K9D6EG2")
PIPELINE_ID = 3840
SLACK_PR_CHANNEL = "C080K9D6EG2"

AUTO_APPROVE_CONFIG_PATH = Path(__file__).parent.parent / "memoria" / "auto_approve_config.json"
BLOCKED_AUTHORS_PATH = Path(__file__).parent.parent / "memoria" / "blocked_authors.json"
BLOCKED_BRANCHES_PATH = Path(__file__).parent.parent / "memoria" / "blocked_branches.json"

def load_auto_approve_config():
    try:
        if AUTO_APPROVE_CONFIG_PATH.exists():
            return json.loads(AUTO_APPROVE_CONFIG_PATH.read_text())
    except Exception as e:
        logger.error("[config] Error leyendo auto_approve_config: %s", e)
    return {"enabled": False, "branches": []}

def save_auto_approve_config(cfg):
    try:
        AUTO_APPROVE_CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))
    except Exception as e:
        logger.error("[config] Error guardando auto_approve_config: %s", e)

def load_blocked_authors():
    try:
        if BLOCKED_AUTHORS_PATH.exists():
            return json.loads(BLOCKED_AUTHORS_PATH.read_text())
    except Exception as e:
        logger.error("[config] Error leyendo blocked_authors: %s", e)
    return ["Glenda Paiva"]

def save_blocked_authors(authors):
    try:
        BLOCKED_AUTHORS_PATH.write_text(json.dumps(authors, indent=2, ensure_ascii=False))
    except Exception as e:
        logger.error("[config] Error guardando blocked_authors: %s", e)

def load_blocked_branches():
    try:
        if BLOCKED_BRANCHES_PATH.exists():
            return json.loads(BLOCKED_BRANCHES_PATH.read_text())
    except Exception as e:
        logger.error("[config] Error leyendo blocked_branches: %s", e)
    return []

def save_blocked_branches(branches):
    try:
        BLOCKED_BRANCHES_PATH.write_text(json.dumps(branches, indent=2, ensure_ascii=False))
    except Exception as e:
        logger.error("[config] Error guardando blocked_branches: %s", e)

TA_SLACK_IDS = {
    "gustavo alonso muciño": "U06JUHG1G9Y",
    "hugo revuelta":         "U07TQ8JNMBR",
    "gabriel alvis":         "U066X49C5NZ",
    "francisco zubizarreta": "U01LXV1UD3K",
    "luís guilherme lino":   "U023L6SJVQW",
    "luis guilherme lino":   "U023L6SJVQW",
}

SLACK_TOKEN = os.getenv("SLACK_TOKEN")
API_KEY = os.getenv("API_KEY")

if not SLACK_TOKEN:
    logger.warning("SLACK_TOKEN no configurado en .env")
if not API_KEY:
    logger.warning("API_KEY no configurado en .env — endpoints de acción sin protección")

# ── Decorador de autenticación por API key ────────────────────────────────────
def require_api_key(f):
    """Protege endpoints de acción con una API key simple.
    Si DASHBOARD_API_KEY no está configurada, permite acceso (modo desarrollo).
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if API_KEY:
            key = request.headers.get("X-API-Key") or request.args.get("api_key")
            if key != API_KEY:
                logger.warning("Intento de acceso sin API key válida a %s", request.path)
                return jsonify({"ok": False, "error": "No autorizado"}), 401
        return f(*args, **kwargs)
    return decorated

# ── Validación de fechas ──────────────────────────────────────────────────────
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

def _validate_date(s):
    """Valida que s sea una fecha YYYY-MM-DD válida. Lanza ValueError si no."""
    if not s or not _DATE_RE.match(s):
        raise ValueError(f"Fecha inválida: {s!r}. Formato esperado: YYYY-MM-DD")
    datetime.strptime(s, "%Y-%m-%d")  # verifica que sea una fecha real
    return s

# ── Retry con backoff exponencial ─────────────────────────────────────────────
def _retry(fn, retries=2, base_delay=0.5, label=""):
    """Ejecuta fn con reintentos y backoff exponencial."""
    for attempt in range(retries):
        try:
            return fn()
        except Exception as e:
            if attempt == retries - 1:
                logger.error("[retry:%s] Falló tras %d intentos: %s", label, retries, e)
                raise
            delay = base_delay * (2 ** attempt)
            logger.warning("[retry:%s] Intento %d/%d falló (%s). Reintentando en %.1fs...",
                           label, attempt + 1, retries, e, delay)
            time.sleep(delay)

app = Flask(__name__)


def run(cmd):
    return subprocess.check_output(cmd, text=True)


def slack_api(method, payload):
    def _call():
        data = json.dumps(payload).encode()
        req = Request(
            f"https://slack.com/api/{method}",
            data=data,
            headers={"Authorization": f"Bearer {SLACK_TOKEN}", "Content-Type": "application/json"},
        )
        with urlopen(req, timeout=5) as r:
            resp = json.loads(r.read())
        if not resp.get("ok"):
            raise RuntimeError(f"Slack API error [{method}]: {resp.get('error', 'unknown')}")
        return resp
    return _retry(_call, retries=2, label=f"slack.{method}")


def find_pr_thread(pr_id, save_if_found=False):
    """Busca el thread_ts del PR. Si save_if_found=True, lo guarda en el estado.
    
    TROUBLESHOOTING: Si los mensajes llegan fuera del hilo:
    - Verificar que el PR esté publicado en Slack (canal C080K9D6EG2)
    - El sistema ahora valida que exista el hilo antes de enviar mensajes
    - Si no encuentra el hilo, registra un warning en los logs
    """
    state = load_state()
    pr_threads = state.setdefault("pr_threads", {})
    
    # Si ya está guardado, usarlo
    if str(pr_id) in pr_threads:
        return pr_threads[str(pr_id)]
    
    # Buscar en Slack
    result = slack_api("conversations.history", {"channel": SLACK_PR_CHANNEL, "limit": 200})
    needle = f"pullrequest/{pr_id}"
    for msg in result.get("messages", []):
        if needle in msg.get("text", ""):
            thread_ts = msg["ts"]
            if save_if_found:
                pr_threads[str(pr_id)] = thread_ts
                save_state(state)
            return thread_ts
        for att in msg.get("attachments", []):
            if needle in att.get("text", "") or needle in att.get("fallback", "") or needle in att.get("title_link", ""):
                thread_ts = msg["ts"]
                if save_if_found:
                    pr_threads[str(pr_id)] = thread_ts
                    save_state(state)
                return thread_ts
        for block in msg.get("blocks", []):
            if needle in json.dumps(block):
                thread_ts = msg["ts"]
                if save_if_found:
                    pr_threads[str(pr_id)] = thread_ts
                    save_state(state)
                return thread_ts
    return None


def wait_for_pr_thread(pr_id, interval=5, max_wait=30):
    """Espera hasta max_wait segundos a que aparezca el hilo del PR en Slack."""
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
            thread_ts = wait_for_pr_thread(pr_id)
            if not thread_ts:
                logger.warning("[slack] No se pudo notificar PR %s (acción: %s): hilo no encontrado", pr_id, action)
                return
            slack_api("chat.postMessage", {"channel": SLACK_PR_CHANNEL, "text": text, "thread_ts": thread_ts})
        except Exception as e:
            logger.error("[slack] Error notificando PR %s (acción: %s): %s", pr_id, action, e)

    threading.Thread(target=_send, daemon=True).start()


def get_pr_ta_reviewers(pr_id, only_pending=True):
    try:
        prs = json.loads(run([
            "az", "repos", "pr", "list", "--status", "active",
            "--repository", REPOSITORY, "--org", ORG_URL, "--project", PROJECT, "-o", "json",
        ]))
        pr = next((p for p in prs if p["pullRequestId"] == int(pr_id)), None)
        if not pr:
            return []
        mentions = []
        for r in pr.get("reviewers", []):
            if only_pending and r.get("vote", 0) == 10:
                continue
            name = (r.get("displayName") or "").lower().strip()
            slack_id = TA_SLACK_IDS.get(name) or next(
                (v for k, v in TA_SLACK_IDS.items() if name.startswith(k) or k.startswith(name)), None
            )
            if slack_id:
                mentions.append(f"<@{slack_id}>")
        return mentions
    except Exception:
        return []


def get_deploy_status(pr_id, merge_commit=None, closed_date=None, target_branch=None):
    """Busca el release asociado al PR via commit de merge o branch del PR.
    Retorna tupla (status, deploy_date) donde deploy_date es ISO string o ''.
    """
    try:
        token = get_token()
        org_name = ORG_URL.rstrip("/").split("/")[-1]
        vsrm = f"https://vsrm.dev.azure.com/{org_name}/{PROJECT}"
        releases = _api_azure(f"{vsrm}/_apis/release/releases?api-version=7.1&$top=50", token).get("value", [])
        pr_branch = f"refs/pull/{pr_id}/merge"

        for rel in releases:
            detail = _api_azure(f"{vsrm}/_apis/release/releases/{rel['id']}?api-version=7.1", token)
            for art in detail.get("artifacts", []):
                ref    = art.get("definitionReference", {})
                branch = ref.get("branch", {}).get("id", "")
                commit = ref.get("sourceVersion", {}).get("id", "")
                # Coincidencia exacta por PR branch (PR activo/CI)
                if branch == pr_branch:
                    return _release_status(detail)
                # Coincidencia exacta por commit de merge (PR completado)
                if merge_commit and commit and commit == merge_commit:
                    return _release_status(detail)
        return "unknown", ""
    except Exception:
        return "unknown", ""


def _api_azure(url, token):
    def _call():
        req = Request(url, headers={"Authorization": f"Bearer {token}"})
        with urlopen(req, timeout=5) as r:
            return json.loads(r.read())
    return _retry(_call, retries=2, label="azure_api")


def _release_status(release):
    """Retorna (status, deploy_date) donde deploy_date es ISO string o ''."""
    envs = release.get("environments", [])
    if not envs:
        return "unknown", ""

    statuses = [e.get("status", "") for e in envs]

    if any(s == "inProgress" for s in statuses):
        return "inProgress", ""

    if any(s == "queued" for s in statuses):
        return "inProgress", ""

    # Ignorar notStarted
    active_envs = [e for e in envs if e.get("status", "") != "notStarted"]
    if not active_envs:
        return "inProgress", ""

    active_statuses = [e.get("status", "") for e in active_envs]

    # Si todos los activos son succeeded/skipped → éxito
    if all(s in ("succeeded", "skipped") for s in active_statuses):
        return "succeeded", _latest_deploy_date(active_envs)

    # Si hay mezcla de succeeded y failed → comparar fechas, gana el más reciente
    has_success = any(s in ("succeeded", "skipped") for s in active_statuses)
    has_failure = any(s in ("rejected", "failed", "canceled") for s in active_statuses)
    if has_success and has_failure:
        success_date = _latest_deploy_date([e for e in active_envs if e.get("status") in ("succeeded", "skipped")])
        failure_date = _latest_deploy_date([e for e in active_envs if e.get("status") in ("rejected", "failed", "canceled")])
        if success_date and failure_date:
            if success_date >= failure_date:
                return "succeeded", success_date
            return "failed", failure_date
        return "succeeded" if success_date else "failed", success_date or failure_date

    if has_failure:
        return "failed", _latest_deploy_date(active_envs)

    return "inProgress", ""


def _latest_deploy_date(envs):
    """Extrae la fecha más reciente de completado entre los environments."""
    dates = []
    for env in envs:
        for attempt in env.get("deploySteps", []):
            d = attempt.get("lastModifiedOn") or attempt.get("queuedOn", "")
            if d:
                dates.append(d)
    return max(dates) if dates else ""


def get_pr_approval_date(pr_id, token):
    """Retorna la fecha del primer voto de aprobación (vote=10) en el PR."""
    try:
        url = f"{ORG_URL}/{PROJECT}/_apis/git/repositories/{REPOSITORY}/pullRequests/{pr_id}/reviewers?api-version=7.1"
        req = Request(url, headers={"Authorization": f"Bearer {token}"})
        with urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
        # Buscar en threads de votos la fecha más temprana de aprobación
        threads_url = f"{ORG_URL}/{PROJECT}/_apis/git/repositories/{REPOSITORY}/pullRequests/{pr_id}/threads?api-version=7.1"
        req2 = Request(threads_url, headers={"Authorization": f"Bearer {token}"})
        with urlopen(req2, timeout=5) as r2:
            threads = json.loads(r2.read())
        dates = []
        for t in threads.get("value", []):
            for c in t.get("comments", []):
                if c.get("commentType") == "system" and "approved" in (c.get("content") or "").lower():
                    d = c.get("publishedDate") or c.get("lastUpdatedDate")
                    if d:
                        dates.append(d)
        return min(dates) if dates else ""
    except Exception:
        return ""


# ── Cache para project_id ────────────────────────────────────────────────────
_project_id_cache = None

def get_pr_policy_status(pr_id, token):
    global _project_id_cache
    try:
        if _project_id_cache is None:
            _project_id_cache = run([
                "az", "devops", "project", "show",
                "--project", PROJECT, "--org", ORG_URL, "--query", "id", "-o", "tsv"
            ]).strip()
        artifact_id = f"vstfs:///CodeReview/CodeReviewId/{_project_id_cache}/{pr_id}"
        url = f"{ORG_URL}/{PROJECT}/_apis/policy/evaluations?artifactId={quote(artifact_id, safe='')}&api-version=7.1-preview.1"
        req = Request(url, headers={"Authorization": f"Bearer {token}"})
        with urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
        statuses = [e.get("status") for e in data.get("value", [])]
        if not statuses:
            return "unknown"
        if any(s == "rejected" for s in statuses):
            return "failed"
        if any(s in ("queued", "running") for s in statuses):
            return "running"
        if all(s == "approved" for s in statuses):
            return "approved"
        return "unknown"
    except Exception:
        return "unknown"


class TokenExpiredError(Exception):
    pass


def _check_token():
    """Obtiene el token y verifica que no esté expirado."""
    try:
        token = get_token()
        # Verificar que el token funciona con una llamada mínima
        result = subprocess.run(
            ["az", "account", "get-access-token", "--resource", "499b84ac-1321-427f-aa17-267ca6975798", "-o", "json"],
            capture_output=True, text=True
        )
        if result.returncode != 0 or "AADSTS" in (result.stderr or "") or "Please run" in (result.stderr or ""):
            raise TokenExpiredError("Token de Azure expirado")
        return token
    except TokenExpiredError:
        raise
    except Exception as e:
        if "AADSTS" in str(e) or "Please run" in str(e) or "az login" in str(e):
            raise TokenExpiredError("Token de Azure expirado")
        raise


def get_prs():
    try:
        token = _check_token()
    except TokenExpiredError:
        raise
    try:
        prs = json.loads(run([
            "az", "repos", "pr", "list", "--status", "active",
            "--repository", REPOSITORY, "--org", ORG_URL, "--project", PROJECT, "-o", "json",
        ]))
    except Exception as e:
        err = str(e)
        if "AADSTS" in err or "Please run" in err or "az login" in err or "token" in err.lower():
            raise TokenExpiredError("Token de Azure expirado")
        logger.error("[get_prs] Error consultando PRs: %s", e)
        raise
    prs = [pr for pr in prs if normalize_ref(pr.get("targetRefName", "")) in {"develop", "develop-pr", "releaseproyecto/r6"}]
    state = load_state()
    seen = state.setdefault("seen", {})
    blocked_authors = [a.lower().strip() for a in load_blocked_authors()]
    blocked_branches = [b.lower().strip() for b in load_blocked_branches()]
    def _collect_pr_data(pr):
        pr_id = str(pr["pullRequestId"])
        source_branch = normalize_ref(pr.get("sourceRefName", "")).lower().strip()
        target_branch = normalize_ref(pr.get("targetRefName", "")).lower().strip()
        # Filtrar solo por rama fuente bloqueada (no por destino — eso es freeze)
        if any(bb in source_branch for bb in blocked_branches if bb and bb not in {"develop", "develop-pr", "releaseproyecto/r6"}):
            return None
        changes = fetch_changes(pr_id, token)
        report = classify(pr, changes, token=token)
        report["creationDate"] = pr.get("creationDate", "")
        report["url"] = f"{ORG_URL}/{PROJECT}/_git/{REPOSITORY}/pullrequest/{pr_id}"
        report["myVote"] = get_my_vote(pr)
        report["blocked"] = (report.get("createdBy") or "").lower().strip() in blocked_authors
        report["frozen"] = any(bb == target_branch for bb in blocked_branches if bb)
        report["hasConflicts"] = pr.get("mergeStatus") == "conflicts"
        policy_status = get_pr_policy_status(pr_id, token)
        report["policyStatus"] = policy_status
        report["canComplete"] = policy_status == "approved"
        report["_targetRefName"] = pr.get("targetRefName", "")
        return report

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(_collect_pr_data, pr): pr for pr in prs}
        collected = []
        for future in as_completed(futures):
            result = future.result()
            if result is not None:
                collected.append(result)

    reports = []
    for report in collected:
        pr_id = str(report["id"])
        policy_status = report["policyStatus"]
        if report["hasConflicts"]:
            report["verdict"] = "resolver conflicto"
            with _state_lock:
                conflicts_notified = state.setdefault("conflicts_notified", [])
                should_notify = int(pr_id) not in conflicts_notified
                if should_notify:
                    conflicts_notified.append(int(pr_id))
                    save_state(state)
            if should_notify:
                def _notify_conflict():
                    try:
                        thread_ts = wait_for_pr_thread(int(pr_id))
                        if thread_ts:
                            slack_api("chat.postMessage", {
                                "channel": SLACK_PR_CHANNEL,
                                "thread_ts": thread_ts,
                                "text": "⚠️ ¡Por favor resolver conflicto!"
                            })
                        else:
                            logger.warning("[conflicts] PR %s: hilo no encontrado, no se notificó", pr_id)
                    except Exception:
                        pass
                threading.Thread(target=_notify_conflict, daemon=True).start()
        elif policy_status == "failed":
            report["verdict"] = "evaluar check"
            with _state_lock:
                check_notified = state.setdefault("check_notified", [])
                should_notify_check = int(pr_id) not in check_notified
                if should_notify_check:
                    check_notified.append(int(pr_id))
                    save_state(state)
            if should_notify_check:
                def _notify_check():
                    try:
                        thread_ts = wait_for_pr_thread(int(pr_id))
                        if thread_ts:
                            slack_api("chat.postMessage", {
                                "channel": SLACK_PR_CHANNEL,
                                "thread_ts": thread_ts,
                                "text": "🔍 Por favor verifica el check del Pull Request"
                            })
                        else:
                            logger.warning("[check] PR %s: hilo no encontrado, no se notificó", pr_id)
                    except Exception:
                        pass
                threading.Thread(target=_notify_check, daemon=True).start()
        elif policy_status == "running" and report["verdict"] not in ("rechazar", "revisar") and report["myVote"] != "approved":
            report["verdict"] = "posible aprobación"

        # Si ya aprobé pero el TA no ha aprobado aún
        if (report["myVote"] == "approved" and not report["canComplete"]
                and not report["hasConflicts"] and policy_status not in ("failed",)):
            report["verdict"] = "TA Reviewer"

        # Auto-aprobación
        auto_cfg = load_auto_approve_config()
        target_branch = normalize_ref(report.pop("_targetRefName", ""))
        if (
            auto_cfg.get("enabled")
            and target_branch in auto_cfg.get("branches", [])
            and not report["hasConflicts"]
            and not report["blocked"]
            and policy_status != "failed"
            and report["verdict"] in ("aprobable", "aprobable con cautela", "posible aprobación")
            and not report["reasons"]
            and not any(".md" in w for w in report.get("warnings", []))
            and report["myVote"] != "approved"
        ):
            with _auto_approve_lock:
                auto_approved = state.setdefault("auto_approved", [])
                if int(pr_id) not in auto_approved or report["myVote"] != "approved":
                    # Si el voto fue reseteado, remover del set para reintentar
                    if int(pr_id) in auto_approved and report["myVote"] != "approved":
                        auto_approved.remove(int(pr_id))
                    try:
                        result = subprocess.run([
                            "az", "repos", "pr", "set-vote", "--id", pr_id,
                            "--vote", "approve", "--org", ORG_URL, "-o", "json"
                        ], capture_output=True, text=True)
                        if result.returncode == 0:
                            logger.info("[auto-approve] PR %s aprobado automáticamente", pr_id)
                            
                            def _notify_auto_approve():
                                thread_ts = wait_for_pr_thread(int(pr_id))
                                if thread_ts:
                                    try:
                                        slack_api("chat.postMessage", {
                                            "channel": SLACK_PR_CHANNEL,
                                            "thread_ts": thread_ts,
                                            "text": "✅ Aprobado"
                                        })
                                    except Exception as se:
                                        logger.error("[auto-approve] Error notificando Slack PR %s: %s", pr_id, se)
                                    
                                    # Notificar al TA para que revise
                                    ta_notified = state.setdefault("ta_notified", [])
                                    if int(pr_id) not in ta_notified:
                                        try:
                                            mentions = get_pr_ta_reviewers(int(pr_id))
                                            text = f"{' '.join(mentions)} TA por favor revisa este PR" if mentions else "TA por favor revisa este PR"
                                            slack_api("chat.postMessage", {
                                                "channel": SLACK_PR_CHANNEL,
                                                "thread_ts": thread_ts,
                                                "text": text
                                            })
                                            with _state_lock:
                                                ta_notified.append(int(pr_id))
                                                save_state(state)
                                        except Exception as te:
                                            logger.error("[auto-approve] Error notificando TA PR %s: %s", pr_id, te)
                                else:
                                    logger.warning("[auto-approve] PR %s: hilo no encontrado, no se notificó", pr_id)
                            
                            threading.Thread(target=_notify_auto_approve, daemon=True).start()
                            auto_approved.append(int(pr_id))
                            report["myVote"] = "approved"
                            report["canComplete"] = True
                        else:
                            logger.warning("[auto-approve] Falló az vote para PR %s: %s",
                                           pr_id, result.stderr or result.stdout)
                    except Exception as e:
                        logger.error("[auto-approve] Excepción aprobando PR %s: %s", pr_id, e)

        reports.append(report)
    save_state(state)
    priority = {"rechazar": 0, "revisar": 1, "aprobable con cautela": 2, "aprobable": 3}
    return sorted(reports, key=lambda x: (1 if x.get("blocked") else 0, priority.get(x["verdict"], 9), x["id"]))


def _get_approval_date(pr_id, token):
    """Obtiene la fecha en que el primer reviewer aprobó el PR via Azure Threads API."""
    try:
        url = (
            f"{ORG_URL}/{PROJECT}/_apis/git/repositories/{REPOSITORY}"
            f"/pullRequests/{pr_id}/threads?api-version=7.1"
        )
        req = Request(url, headers={"Authorization": f"Bearer {token}"})
        with urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
        # Buscar el primer voto de aprobación (vote=10) en los threads
        earliest = None
        for thread in data.get("value", []):
            for comment in thread.get("comments", []):
                props = comment.get("usedCommentType", "")
                # Los votos de aprobación aparecen como tipo "system"
                if comment.get("commentType") == "system":
                    content = comment.get("content", "")
                    if "approved" in content.lower() or "aprobó" in content.lower():
                        pub = comment.get("publishedDate", "")
                        if pub and (earliest is None or pub < earliest):
                            earliest = pub
        return earliest or ""
    except Exception:
        return ""


def prs_completed_by_date(date_from, date_to):
    prs = json.loads(run([
        "az", "repos", "pr", "list", "--status", "completed",
        "--repository", REPOSITORY, "--org", ORG_URL, "--project", PROJECT,
        "--top", "100", "-o", "json",
    ]))
    return [
        {
            "id": p["pullRequestId"], "title": p["title"],
            "createdBy": p.get("createdBy", {}).get("displayName", ""),
            "target": normalize_ref(p.get("targetRefName", "")),
            "closedDate": p.get("closedDate", ""),
            "creationDate": p.get("creationDate", ""),
            "mergeCommit": p.get("lastMergeCommit", {}).get("commitId", ""),
            "url": f"{ORG_URL}/{PROJECT}/_git/{REPOSITORY}/pullrequest/{p['pullRequestId']}",
            "hasConflicts": p.get("mergeStatus") == "conflicts",
            "policyStatus": "",   # se enriquece en export si se necesita
            "reviewers": p.get("reviewers", []),
            "blocked": False,
        }
        for p in prs if date_from <= p.get("closedDate", "")[:10] <= date_to
    ]


@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    """Lanza az login en background y abre el browser para reautenticar."""
    def _run():
        subprocess.run([
            "az", "login", "--allow-no-subscriptions",
            "--tenant", "46bb22b8-4c2c-40ff-8360-7b6334821279"
        ])
    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"ok": True})


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health")
def health():
    return jsonify({"ok": True, "status": "healthy", "ts": datetime.now(timezone.utc).isoformat()})


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
        from datetime import timedelta
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
        try:
            _validate_date(date_from)
            _validate_date(date_to)
        except ValueError as ve:
            return jsonify({"ok": False, "error": str(ve)}), 400
        if date_from > date_to:
            return jsonify({"ok": False, "error": "'from' no puede ser posterior a 'to'"}), 400
        return jsonify({"ok": True, "prs": prs_completed_by_date(date_from, date_to)})
    except Exception as e:
        logger.error("[api/prs/range] %s", e, exc_info=True)
        return jsonify({"ok": False, "error": "Error consultando rango de PRs"}), 500


@app.route("/api/history")
def api_history():
    try:
        today = datetime.now(timezone.utc).date().isoformat()
        date_from = request.args.get("from", today).strip()
        date_to   = request.args.get("to", today).strip()
        _validate_date(date_from)
        _validate_date(date_to)
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
            approval_date = _get_approval_date(pr_id, token) or pr.get("closedDate", "")
            deploy_st, deploy_date = get_deploy_status(
                pr_id, pr.get("mergeCommit"), pr.get("closedDate"), pr.get("target")
            )
            rows.append(_pr_to_row(pr, deploy_status=deploy_st, deploy_date=deploy_date,
                                   approval_date=approval_date, auto_approved=pr_id in auto_approved_ids))
        return jsonify({"ok": True, "headers": SHEET_HEADERS, "rows": rows})
    except Exception as e:
        logger.error("[api/history] %s", e, exc_info=True)
        return jsonify({"ok": False, "error": "Error consultando historial"}), 500


@app.route("/api/pr/<int:pr_id>/approve", methods=["POST"])
@require_api_key
def approve(pr_id):
    # TROUBLESHOOTING: Si falla con "Error al aprobar el PR":
    # 1. Verificar que el PR esté activo (no completado)
    # 2. Si es token expirado: az login --allow-no-subscriptions --tenant "46bb22b8-4c2c-40ff-8360-7b6334821279"
    try:
        result = subprocess.run([
            "az", "repos", "pr", "set-vote", "--id", str(pr_id),
            "--vote", "approve", "--org", ORG_URL, "-o", "json"
        ], capture_output=True, text=True)
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
                        logger.warning("[approve] No se encontró hilo para PR %s al notificar TA", pr_id)
                        return
                    mentions = get_pr_ta_reviewers(pr_id)
                    text = f"{' '.join(mentions)} TA por favor revisa este PR" if mentions else "TA por favor revisa este PR"
                    slack_api("chat.postMessage", {
                        "channel": SLACK_PR_CHANNEL,
                        "thread_ts": thread_ts,
                        "text": text
                    })
                    ta_notified.append(pr_id)
                    save_state(state2)
            except Exception as e:
                logger.error("[approve] Error notificando TA para PR %s: %s", pr_id, e)
        threading.Thread(target=_notify_ta, daemon=True).start()
        logger.info("[approve] PR %s aprobado", pr_id)
        return jsonify({"ok": True, "ta_notified": True})
    except Exception as e:
        logger.error("[approve] PR %s excepción: %s", pr_id, e, exc_info=True)
        return jsonify({"ok": False, "error": "Error interno al aprobar"}), 500


@app.route("/api/pr/<int:pr_id>/reject", methods=["POST"])
@require_api_key
def reject(pr_id):
    try:
        data = request.get_json(silent=True) or {}
        comment = str(data.get("comment", "PR rechazado por revisión automática."))
        # Validar longitud del comentario
        if len(comment) > 2000:
            return jsonify({"ok": False, "error": "Comentario demasiado largo (máx 2000 caracteres)"}), 400
        result = subprocess.run([
            "az", "repos", "pr", "set-vote", "--id", str(pr_id),
            "--vote", "reject", "--org", ORG_URL, "-o", "json"
        ], capture_output=True, text=True)
        if result.returncode != 0:
            logger.error("[reject] PR %s falló: %s", pr_id, result.stderr)
            return jsonify({"ok": False, "error": "Error al rechazar el PR"}), 500
        subprocess.run([
            "az", "repos", "pr", "comment", "add", "--id", str(pr_id),
            "--comment", comment, "--org", ORG_URL, "--project", PROJECT, "-o", "none"
        ])
        notify_pr_slack(pr_id, "reject", comment)
        logger.info("[reject] PR %s rechazado", pr_id)
        return jsonify({"ok": True})
    except Exception as e:
        logger.error("[reject] PR %s excepción: %s", pr_id, e, exc_info=True)
        return jsonify({"ok": False, "error": "Error interno al rechazar"}), 500


def _poll_deploy_background(pr_id, merge_commit, closed_date, target_branch, author=None):
    """Polling de despliegue en background, independiente del navegador."""
    def _run():
        if author and author.lower().strip() in [a.lower().strip() for a in load_blocked_authors()]:
            return
        logger.info("[deploy-poll] Iniciando polling para PR %s", pr_id)
        for attempt in range(60):  # máx 60 intentos = ~1 hora
            time.sleep(60)
            # Re-verificar bloqueo en cada ciclo
            if author and author.lower().strip() in [a.lower().strip() for a in load_blocked_authors()]:
                logger.info("[deploy-poll] PR %s: autor bloqueado, deteniendo polling", pr_id)
                return
            try:
                status, deploy_date_bg = get_deploy_status(pr_id, merge_commit, closed_date, target_branch)
                if status in ("succeeded", "failed"):
                    with _state_lock:
                        state = load_state()
                        deploy_notified = state.setdefault("deploy_notified", [])
                        already = int(pr_id) in [int(x) for x in deploy_notified]
                        if not already:
                            deploy_notified.append(int(pr_id))
                            save_state(state)
                    is_blocked_now = author and author.lower().strip() in [a.lower().strip() for a in load_blocked_authors()]
                    if not already and not is_blocked_now:
                        text = "✅ Despliegue completado" if status == "succeeded" else "❌ Despliegue fallido"
                        thread_ts = find_pr_thread(pr_id, save_if_found=True)
                        if not thread_ts:
                            logger.warning("[deploy-poll] PR %s: hilo no encontrado, reintentando", pr_id)
                            continue
                        try:
                            slack_api("chat.postMessage", {
                                "channel": SLACK_PR_CHANNEL, "text": text, "thread_ts": thread_ts
                            })
                        except Exception as se:
                            logger.error("[deploy-poll] Error notificando Slack PR %s: %s", pr_id, se)
                    final_date = deploy_date_bg or datetime.now(timezone.utc).isoformat()
                    _sheet_update_deploy(pr_id, status, final_date)
                    logger.info("[deploy-poll] PR %s: deploy %s", pr_id, status)
                    return
            except Exception as e:
                logger.warning("[deploy-poll] PR %s intento %d error: %s", pr_id, attempt + 1, e)
        logger.warning("[deploy-poll] PR %s: timeout tras 60 intentos", pr_id)
    threading.Thread(target=_run, daemon=True).start()


@app.route("/api/pr/<int:pr_id>/complete", methods=["POST"])
@require_api_key
def complete(pr_id):
    try:
        state = load_state()
        completed_notified = state.setdefault("completed_notified", [])
        result = subprocess.run([
            "az", "repos", "pr", "update", "--id", str(pr_id),
            "--status", "completed", "--org", ORG_URL, "-o", "json"
        ], capture_output=True, text=True)
        if result.returncode != 0:
            logger.error("[complete] PR %s falló: %s", pr_id, result.stderr)
            return jsonify({"ok": False, "error": "Error al completar el PR"}), 500
        pr_data = {}
        if result.stdout.strip().startswith("{"):
            try:
                pr_data = json.loads(result.stdout)
            except json.JSONDecodeError as je:
                logger.warning("[complete] PR %s: respuesta JSON inválida: %s", pr_id, je)
        author = pr_data.get("createdBy", {}).get("displayName", "")
        blocked_authors = [a.lower().strip() for a in load_blocked_authors()]
        is_blocked = author.lower().strip() in blocked_authors
        if not is_blocked and pr_id not in completed_notified:
            notify_pr_slack(pr_id, "complete")
            completed_notified.append(pr_id)
            save_state(state)
        merge_commit  = pr_data.get("lastMergeCommit", {}).get("commitId")
        closed_date   = pr_data.get("closedDate", "")
        target_branch = pr_data.get("targetRefName", "")
        _poll_deploy_background(pr_id, merge_commit, closed_date, target_branch, author=author)
        state = load_state()
        token = get_token()
        approval_date = get_pr_approval_date(pr_id, token)
        policy_status = get_pr_policy_status(pr_id, token)
        sheet_pr = {
            "pullRequestId": pr_id,
            "title": pr_data.get("title", ""),
            "createdBy": pr_data.get("createdBy", {}).get("displayName", ""),
            "targetRefName": target_branch,
            "creationDate": pr_data.get("creationDate", ""),
            "closedDate": closed_date,
            "hasConflicts": pr_data.get("mergeStatus") == "conflicts",
            "policyStatus": policy_status,
        }
        _sheet_append_pr(sheet_pr, auto_approved=pr_id in state.get("auto_approved", []), approval_date=approval_date)
        logger.info("[complete] PR %s completado", pr_id)
        return jsonify({"ok": True})
    except Exception as e:
        logger.error("[complete] PR %s excepción: %s", pr_id, e, exc_info=True)
        return jsonify({"ok": False, "error": "Error interno al completar"}), 500


@app.route("/api/pr/<int:pr_id>/notify-deploy", methods=["POST"])
@require_api_key
def notify_deploy(pr_id):
    try:
        with _state_lock:
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
        text   = "✅ Despliegue completado" if status == "succeeded" else "❌ Despliegue fallido"
        thread_ts = find_pr_thread(pr_id, save_if_found=True)
        if not thread_ts:
            return jsonify({"ok": False, "error": f"No se encontró el hilo del PR {pr_id}"}), 404
        slack_api("chat.postMessage", {"channel": SLACK_PR_CHANNEL, "text": text, "thread_ts": thread_ts})
        return jsonify({"ok": True})
    except Exception as e:
        logger.error("[notify-deploy] PR %s excepción: %s", pr_id, e, exc_info=True)
        return jsonify({"ok": False, "error": "Error interno al notificar deploy"}), 500


@app.route("/api/pr/<int:pr_id>/deploy-status")
def deploy_status(pr_id):
    try:
        merge_commit  = request.args.get("mergeCommit", "")
        closed_date   = request.args.get("closedDate", "")
        target_branch = request.args.get("target", "")
        status, _ = get_deploy_status(pr_id, merge_commit, closed_date, target_branch)
        return jsonify({"ok": True, "status": status})
    except Exception as e:
        logger.error("[deploy-status] PR %s excepción: %s", pr_id, e, exc_info=True)
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
        mentions = get_pr_ta_reviewers(pr_id) or []
        text = f"{' '.join(mentions)} TA por favor revisa este PR" if mentions else "TA por favor revisa este PR"
        slack_api("chat.postMessage", {
            "channel": SLACK_PR_CHANNEL, "thread_ts": thread_ts, "text": text
        })
        ta_notified.append(pr_id)
        save_state(state)
        return jsonify({"ok": True})
    except Exception as e:
        logger.error("[request-ta-approval] PR %s excepción: %s", pr_id, e, exc_info=True)
        return jsonify({"ok": False, "error": "Error interno al notificar TA"}), 500


@app.route("/api/config/auto-approve", methods=["GET"])
def get_auto_approve_config():
    return jsonify(load_auto_approve_config())

@app.route("/api/config/auto-approve", methods=["POST"])
@require_api_key
def set_auto_approve_config():
    try:
        data = request.get_json(silent=True) or {}
        cfg = load_auto_approve_config()
        if "enabled" in data:
            cfg["enabled"] = bool(data["enabled"])
        if "branches" in data:
            branches = list(data["branches"])
            # Validar que sean strings no vacíos
            cfg["branches"] = [str(b).strip() for b in branches if str(b).strip()]
        save_auto_approve_config(cfg)
        return jsonify({"ok": True, "config": cfg})
    except Exception as e:
        logger.error("[config/auto-approve] %s", e, exc_info=True)
        return jsonify({"ok": False, "error": "Error guardando configuración"}), 500


@app.route("/api/config/blocked-authors", methods=["GET"])
def get_blocked_authors():
    return jsonify(load_blocked_authors())

@app.route("/api/config/blocked-authors", methods=["POST"])
@require_api_key
def set_blocked_authors():
    try:
        data = request.get_json(silent=True) or {}
        authors = list(data.get("authors", []))
        # Validar: solo strings, máx 200 chars cada uno, máx 100 autores
        validated = []
        for a in authors:
            a = str(a).strip()
            if a and len(a) <= 200:
                validated.append(a)
        if len(validated) > 100:
            return jsonify({"ok": False, "error": "Máximo 100 autores bloqueados"}), 400
        save_blocked_authors(validated)
        return jsonify({"ok": True, "authors": validated})
    except Exception as e:
        logger.error("[config/blocked-authors] %s", e, exc_info=True)
        return jsonify({"ok": False, "error": "Error guardando autores bloqueados"}), 500


@app.route("/api/config/blocked-branches", methods=["GET"])
def get_blocked_branches():
    return jsonify(load_blocked_branches())

@app.route("/api/config/blocked-branches", methods=["POST"])
@require_api_key
def set_blocked_branches():
    try:
        data = request.get_json(silent=True) or {}
        branches = list(data.get("branches", []))
        validated = []
        for b in branches:
            b = str(b).strip()
            if b and len(b) <= 200:
                validated.append(b)
        if len(validated) > 100:
            return jsonify({"ok": False, "error": "Máximo 100 ramas bloqueadas"}), 400
        save_blocked_branches(validated)
        return jsonify({"ok": True, "branches": validated})
    except Exception as e:
        logger.error("[config/blocked-branches] %s", e, exc_info=True)
        return jsonify({"ok": False, "error": "Error guardando ramas bloqueadas"}), 500


@app.route("/api/branches")
def api_branches():
    return jsonify({"ok": True, "branches": ["develop", "develop-pr", "releaseproyecto/r6"]})


@app.route("/api/branch/create", methods=["POST"])
def create_branch():
    try:
        data = request.get_json(silent=True) or {}
        branch_name = str(data.get("name", "")).strip()
        base_branch = str(data.get("base", "develop")).strip()
        if not branch_name:
            return jsonify({"ok": False, "error": "Nombre de rama requerido"}), 400
        result = subprocess.run([
            "az", "repos", "ref", "create",
            "--name", f"refs/heads/{branch_name}",
            "--object-id", _get_branch_object_id(base_branch),
            "--repository", REPOSITORY,
            "--org", ORG_URL,
            "--project", PROJECT,
            "-o", "json"
        ], capture_output=True, text=True)
        if result.returncode != 0:
            return jsonify({"ok": False, "error": result.stderr or result.stdout}), 500
        return jsonify({"ok": True, "branch": branch_name})
    except Exception as e:
        logger.error("[branch/create] %s", e, exc_info=True)
        return jsonify({"ok": False, "error": str(e)}), 500


def _get_branch_object_id(branch_name):
    token = get_token()
    url = f"{ORG_URL}/{PROJECT}/_apis/git/repositories/{REPOSITORY}/refs?filter=heads/{branch_name}&api-version=7.1"
    req = Request(url, headers={"Authorization": f"Bearer {token}"})
    with urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    return data["value"][0]["objectId"]



@app.route("/api/stats")
def api_stats():
    try:
        from datetime import timedelta
        today = datetime.now(timezone.utc).date().isoformat()
        yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()

        active_prs = get_prs()
        active_count = len(active_prs)
        conflicts_count = sum(1 for p in active_prs if p.get("hasConflicts"))

        completed_today = prs_completed_by_date(today, today)
        completed_count = len(completed_today)

        completed_yesterday = prs_completed_by_date(yesterday, yesterday)
        yesterday_count = len(completed_yesterday)

        review_times = []
        for pr in completed_today:
            t = _minutes_between(pr.get("creationDate", ""), pr.get("closedDate", ""))
            if isinstance(t, (int, float)) and t > 0:
                review_times.append(t)
        avg_review_min = round(sum(review_times) / len(review_times)) if review_times else 0

        state = load_state()
        auto_approved_ids = set(state.get("auto_approved", []))
        auto_rate = 0
        if completed_count > 0:
            auto_in_today = sum(1 for pr in completed_today if pr["id"] in auto_approved_ids)
            auto_rate = round(auto_in_today / completed_count * 100)

        trend = completed_count - yesterday_count

        return jsonify({
            "ok": True,
            "stats": {
                "active": active_count,
                "completed_today": completed_count,
                "completed_yesterday": yesterday_count,
                "trend": trend,
                "conflicts": conflicts_count,
                "avg_review_min": avg_review_min,
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
        date_from = str(data.get("from", "")).strip()
        date_to   = str(data.get("to", "")).strip()
        if not date_from or not date_to:
            today = datetime.now(timezone.utc).date().isoformat()
            date_from = date_to = today
        else:
            try:
                _validate_date(date_from)
                _validate_date(date_to)
            except ValueError as ve:
                return jsonify({"ok": False, "error": str(ve)}), 400

        prs = prs_completed_by_date(date_from, date_to)
        state = load_state()
        auto_approved_ids = set(state.get("auto_approved", []))
        blocked_authors = [a.lower().strip() for a in load_blocked_authors()]
        token = get_token()

        rows = [SHEET_HEADERS]
        for pr in prs:
            pr_id = pr["id"]
            pr["blocked"] = (pr.get("createdBy") or "").lower().strip() in blocked_authors
            try:
                pr["policyStatus"] = get_pr_policy_status(pr_id, token)
            except Exception:
                pr["policyStatus"] = ""

            approval_date = _get_approval_date(pr_id, token)
            if not approval_date:
                approval_date = pr.get("closedDate", "")

            deploy_st, deploy_date = get_deploy_status(
                pr_id, pr.get("mergeCommit"), pr.get("closedDate"), pr.get("target")
            )

            rows.append(_pr_to_row(
                pr,
                deploy_status=deploy_st,
                deploy_date=deploy_date,
                approval_date=approval_date,
                auto_approved=pr_id in auto_approved_ids,
            ))

        def _do_export():
            svc = _sheets_service()
            sheet = svc.spreadsheets()
            # Leer filas existentes para preservar historial
            existing = sheet.values().get(
                spreadsheetId=SHEET_ID, range="Hoja 1"
            ).execute().get("values", [])
            # Índice de PR ID en la fila (columna A = índice 0)
            existing_ids = {r[0] for r in existing[1:] if r} if len(existing) > 1 else set()
            # Solo agregar filas nuevas (excluir header y duplicados)
            new_rows = [r for r in rows[1:] if str(r[0]) not in existing_ids]
            if not new_rows:
                return
            # Agregar al final
            sheet.values().append(
                spreadsheetId=SHEET_ID,
                range="Hoja 1",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": new_rows},
            ).execute()
        _retry(_do_export, retries=3, label="sheets.export")

        logger.info("[export-sheets] %d filas exportadas (%s → %s)", len(rows) - 1, date_from, date_to)
        return jsonify({"ok": True, "rows": len(rows) - 1})
    except Exception as e:
        logger.error("[export-sheets] %s", e, exc_info=True)
        return jsonify({"ok": False, "error": "Error exportando a Sheets"}), 500


LOCAL_REPO = Path("/home/zen6/cc/SalesForce")

def _git_fetch_loop():
    """Hace git fetch cada 5 minutos usando el token de az cli para autenticación."""
    while True:
        try:
            # Obtener token de az cli (mismo que usa el resto de la app)
            tok = subprocess.run(
                ["az", "account", "get-access-token",
                 "--resource", "499b84ac-1321-427f-aa17-267ca6975798", "-o", "json"],
                capture_output=True, text=True, timeout=15,
            )
            if tok.returncode != 0:
                logger.debug("[git-fetch] no se pudo obtener token az, omitiendo fetch")
                time.sleep(300)
                continue

            access_token = json.loads(tok.stdout).get("accessToken", "")
            # Pasar credencial via credential helper que responde con el token
            credential_script = f"#!/bin/sh\necho username=x-access-token\necho password={access_token}\n"
            cred_path = Path("/tmp/_git_cred_helper.sh")
            cred_path.write_text(credential_script)
            cred_path.chmod(0o700)

            result = subprocess.run(
                ["git", "-C", str(LOCAL_REPO),
                 "-c", f"credential.helper={cred_path}",
                 "fetch", "origin", "--prune"],
                capture_output=True, timeout=30,
                env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
            )
            if result.returncode == 0:
                logger.info("[git-fetch] fetch completado")
            else:
                logger.debug("[git-fetch] fetch falló (rc=%d): %s",
                             result.returncode, result.stderr.decode().strip())
        except subprocess.TimeoutExpired:
            logger.debug("[git-fetch] timeout, se reintentará en 5 min")
        except Exception as e:
            logger.debug("[git-fetch] error: %s", e)
        time.sleep(300)


if __name__ == "__main__":
    threading.Thread(target=_git_fetch_loop, daemon=True).start()
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", debug=debug_mode, port=5000, threaded=True)
