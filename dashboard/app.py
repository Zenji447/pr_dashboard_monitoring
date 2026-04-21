#!/usr/bin/env python3
import json
import logging
import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen
from flask import Flask, jsonify, render_template, request, abort

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

SHEET_ID = "1jsYHmGm-2eN5986bgN5jlPO86guNfWmnf980H4TsdO0"
CREDS_PATH = Path(__file__).parent.parent / "google_credentials.json"
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
            _retry(_do, retries=3, label="sheets.append")
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
            _retry(_do, retries=3, label="sheets.update_deploy")
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

ORG_URL = "https://dev.azure.com/OrgClaroColombia"
PROJECT = "SalesForce"
REPOSITORY = "SalesForce"
PIPELINE_ID = 3840
SLACK_PR_CHANNEL = "C080K9D6EG2"

AUTO_APPROVE_CONFIG_PATH = Path(__file__).parent.parent / "memoria" / "auto_approve_config.json"
BLOCKED_AUTHORS_PATH = Path(__file__).parent.parent / "memoria" / "blocked_authors.json"

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

TA_SLACK_IDS = {
    "gustavo alonso muciño": "U06JUHG1G9Y",
    "hugo revuelta":         "U07TQ8JNMBR",
    "gabriel alvis":         "U066X49C5NZ",
    "francisco zubizarreta": "U01LXV1UD3K",
    "luís guilherme lino":   "U023L6SJVQW",
    "luis guilherme lino":   "U023L6SJVQW",
}

SLACK_TOKEN = None
API_KEY = None  # Clave para proteger endpoints de acción

def _load_env():
    global SLACK_TOKEN, API_KEY
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line.startswith("SLACK_TOKEN="):
                SLACK_TOKEN = line.split("=", 1)[1].strip()
            elif line.startswith("DASHBOARD_API_KEY="):
                API_KEY = line.split("=", 1)[1].strip()
    # También aceptar desde variables de entorno del sistema
    if not SLACK_TOKEN:
        SLACK_TOKEN = os.environ.get("SLACK_TOKEN")
    if not API_KEY:
        API_KEY = os.environ.get("DASHBOARD_API_KEY")

_load_env()

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
def _retry(fn, retries=3, base_delay=2, label=""):
    """Ejecuta fn con reintentos y backoff exponencial."""
    for attempt in range(retries):
        try:
            return fn()
        except Exception as e:
            if attempt == retries - 1:
                logger.error("[retry:%s] Falló tras %d intentos: %s", label, retries, e)
                raise
            delay = base_delay * (2 ** attempt)
            logger.warning("[retry:%s] Intento %d/%d falló (%s). Reintentando en %ds...",
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
        with urlopen(req, timeout=10) as r:
            resp = json.loads(r.read())
        if not resp.get("ok"):
            raise RuntimeError(f"Slack API error [{method}]: {resp.get('error', 'unknown')}")
        return resp
    return _retry(_call, retries=3, label=f"slack.{method}")


def find_pr_thread(pr_id, save_if_found=False):
    """Busca el thread_ts del PR. Si save_if_found=True, lo guarda en el estado."""
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


def wait_for_pr_thread(pr_id, interval=15, max_wait=600):
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
        with urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    return _retry(_call, retries=3, label="azure_api")


def _release_status(release):
    """Retorna (status, deploy_date) donde deploy_date es ISO string o ''."""
    envs = release.get("environments", [])
    if not envs:
        return "unknown", ""

    statuses = [e.get("status", "") for e in envs]

    if any(s == "inProgress" for s in statuses):
        return "inProgress", ""

    if any(s in ("rejected", "failed", "canceled") for s in statuses):
        # Fecha del último deploy fallido
        date = _latest_deploy_date(envs)
        return "failed", date

    # Ignorar notStarted — para PRs solo corre el Checkonly y el otro queda notStarted
    active = [s for s in statuses if s != "notStarted"]
    if active and all(s in ("succeeded", "skipped") for s in active):
        date = _latest_deploy_date(envs)
        return "succeeded", date

    if any(s == "queued" for s in statuses):
        return "inProgress", ""

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
        with urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
        # Buscar en threads de votos la fecha más temprana de aprobación
        threads_url = f"{ORG_URL}/{PROJECT}/_apis/git/repositories/{REPOSITORY}/pullRequests/{pr_id}/threads?api-version=7.1"
        req2 = Request(threads_url, headers={"Authorization": f"Bearer {token}"})
        with urlopen(req2, timeout=15) as r2:
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


def get_pr_policy_status(pr_id, token):
    try:
        project_id = run([
            "az", "devops", "project", "show",
            "--project", PROJECT, "--org", ORG_URL, "--query", "id", "-o", "tsv"
        ]).strip()
        artifact_id = f"vstfs:///CodeReview/CodeReviewId/{project_id}/{pr_id}"
        url = f"{ORG_URL}/{PROJECT}/_apis/policy/evaluations?artifactId={quote(artifact_id, safe='')}&api-version=7.1-preview.1"
        req = Request(url, headers={"Authorization": f"Bearer {token}"})
        with urlopen(req, timeout=15) as r:
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


def get_prs():
    token = get_token()
    prs = json.loads(run([
        "az", "repos", "pr", "list", "--status", "active",
        "--repository", REPOSITORY, "--org", ORG_URL, "--project", PROJECT, "-o", "json",
    ]))
    prs = [pr for pr in prs if normalize_ref(pr.get("targetRefName", "")) in {"develop", "develop-pr", "releaseproyecto/r6"}]
    state = load_state()
    seen = state.setdefault("seen", {})
    blocked_authors = [a.lower().strip() for a in load_blocked_authors()]
    reports = []
    for pr in prs:
        pr_id = str(pr["pullRequestId"])
        changes = fetch_changes(pr_id, token)
        report = classify(pr, changes, token=token)
        report["creationDate"] = pr.get("creationDate", "")
        report["url"] = f"{ORG_URL}/{PROJECT}/_git/{REPOSITORY}/pullrequest/{pr_id}"
        report["myVote"] = get_my_vote(pr)
        report["blocked"] = (report.get("createdBy") or "").lower().strip() in blocked_authors
        report["hasConflicts"] = pr.get("mergeStatus") == "conflicts"
        policy_status = get_pr_policy_status(pr_id, token)
        report["policyStatus"] = policy_status
        report["canComplete"] = policy_status == "approved"
        if report["hasConflicts"]:
            report["verdict"] = "resolver conflicto"
            conflicts_notified = state.setdefault("conflicts_notified", [])
            if int(pr_id) not in conflicts_notified:
                try:
                    thread_ts = wait_for_pr_thread(int(pr_id))
                    slack_api("chat.postMessage", {
                        "channel": SLACK_PR_CHANNEL,
                        "thread_ts": thread_ts,
                        "text": "⚠️ ¡Por favor resolver conflicto!"
                    })
                    conflicts_notified.append(int(pr_id))
                except Exception:
                    pass
        elif policy_status == "failed":
            report["verdict"] = "evaluar check"
        elif policy_status == "running" and report["verdict"] not in ("rechazar", "revisar"):
            report["verdict"] = "posible aprobación"

        # Si ya aprobé pero el TA no ha aprobado aún
        if (report["myVote"] == "approved" and not report["canComplete"]
                and not report["hasConflicts"] and policy_status not in ("failed", "running")):
            report["verdict"] = "TA Reviewer"

        # Auto-aprobación
        auto_cfg = load_auto_approve_config()
        target_branch = normalize_ref(pr.get("targetRefName", ""))
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
                        thread_ts = find_pr_thread(int(pr_id), save_if_found=True)
                        payload = {"channel": SLACK_PR_CHANNEL, "text": "✅ Aprobado"}
                        if thread_ts:
                            payload["thread_ts"] = thread_ts
                        slack_api("chat.postMessage", payload)
                        # Notificar al TA para que revise
                        ta_notified = state.setdefault("ta_notified", [])
                        if int(pr_id) not in ta_notified:
                            mentions = get_pr_ta_reviewers(int(pr_id))
                            text = f"{' '.join(mentions)} TA por favor revisa este PR" if mentions else "TA por favor revisa este PR"
                            slack_api("chat.postMessage", {
                                "channel": SLACK_PR_CHANNEL,
                                "thread_ts": thread_ts,
                                "text": text
                            })
                            ta_notified.append(int(pr_id))
                        auto_approved.append(int(pr_id))
                        report["myVote"] = "approved"
                        report["canComplete"] = True
                except Exception:
                    pass

        reports.append(report)
    save_state(state)
    priority = {"rechazar": 0, "revisar": 1, "aprobable con cautela": 2, "aprobable": 3}
    return sorted(reports, key=lambda x: (priority.get(x["verdict"], 9), x["id"]))


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


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/prs")
def api_prs():
    try:
        return jsonify({"ok": True, "prs": get_prs()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/prs/completed")
def api_prs_completed():
    try:
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).date().isoformat()
        return jsonify({"ok": True, "prs": prs_completed_by_date(today, today)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/prs/completed/yesterday")
def api_prs_yesterday():
    try:
        from datetime import datetime, timezone, timedelta
        yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
        return jsonify({"ok": True, "prs": prs_completed_by_date(yesterday, yesterday)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/prs/completed/range")
def api_prs_range():
    try:
        date_from = request.args.get("from", "")
        date_to   = request.args.get("to", "")
        if not date_from or not date_to:
            return jsonify({"ok": False, "error": "Parámetros 'from' y 'to' requeridos (YYYY-MM-DD)"}), 400
        return jsonify({"ok": True, "prs": prs_completed_by_date(date_from, date_to)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/pr/<int:pr_id>/approve", methods=["POST"])
def approve(pr_id):
    try:
        result = subprocess.run([
            "az", "repos", "pr", "set-vote", "--id", str(pr_id),
            "--vote", "approve", "--org", ORG_URL, "-o", "json"
        ], capture_output=True, text=True)
        if result.returncode != 0:
            return jsonify({"ok": False, "error": result.stderr or result.stdout}), 500
        state = load_state()
        approved_notified = state.setdefault("approved_notified", [])
        if pr_id not in approved_notified:
            notify_pr_slack(pr_id, "approve")
            approved_notified.append(pr_id)
            save_state(state)
        # Notificar al TA si aún no se ha hecho (en background para no bloquear)
        def _notify_ta():
            state = load_state()
            ta_notified = state.setdefault("ta_notified", [])
            if pr_id not in ta_notified:
                thread_ts = wait_for_pr_thread(pr_id, interval=5)  # polling cada 5 seg, máx ~2 min
                mentions = get_pr_ta_reviewers(pr_id)
                text = f"{' '.join(mentions)} TA por favor revisa este PR" if mentions else "TA por favor revisa este PR"
                slack_api("chat.postMessage", {
                    "channel": SLACK_PR_CHANNEL,
                    "thread_ts": thread_ts,
                    "text": text
                })
                ta_notified.append(pr_id)
                save_state(state)
        
        threading.Thread(target=_notify_ta, daemon=True).start()
        ta_sent = True  # Siempre retorna true porque se notificará en background
        return jsonify({"ok": True, "ta_notified": ta_sent})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/pr/<int:pr_id>/reject", methods=["POST"])
def reject(pr_id):
    try:
        data = request.get_json(silent=True) or {}
        comment = data.get("comment", "PR rechazado por revisión automática.")
        result = subprocess.run([
            "az", "repos", "pr", "set-vote", "--id", str(pr_id),
            "--vote", "reject", "--org", ORG_URL, "-o", "json"
        ], capture_output=True, text=True)
        if result.returncode != 0:
            return jsonify({"ok": False, "error": result.stderr or result.stdout}), 500
        subprocess.run([
            "az", "repos", "pr", "comment", "add", "--id", str(pr_id),
            "--comment", comment, "--org", ORG_URL, "--project", PROJECT, "-o", "none"
        ])
        notify_pr_slack(pr_id, "reject", comment)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


def _poll_deploy_background(pr_id, merge_commit, closed_date, target_branch, author=None):
    """Polling de despliegue en background, independiente del navegador."""
    def _run():
        blocked_authors = [a.lower().strip() for a in load_blocked_authors()]
        if author and author.lower().strip() in blocked_authors:
            return
        for _ in range(60):  # máx 60 intentos = ~1 hora
            time.sleep(60)
            try:
                status, deploy_date_bg = get_deploy_status(pr_id, merge_commit, closed_date, target_branch)
                if status in ("succeeded", "failed"):
                    state = load_state()
                    deploy_notified = state.setdefault("deploy_notified", [])
                    if pr_id not in deploy_notified:
                        text = "✅ Despliegue completado" if status == "succeeded" else "❌ Despliegue fallido"
                        thread_ts = find_pr_thread(pr_id, save_if_found=True)
                        if not thread_ts:
                            continue  # reintentar hasta encontrar el hilo
                        slack_api("chat.postMessage", {"channel": SLACK_PR_CHANNEL, "text": text, "thread_ts": thread_ts})
                        deploy_notified.append(pr_id)
                        save_state(state)
                    from datetime import datetime, timezone
                    final_date = deploy_date_bg or datetime.now(timezone.utc).isoformat()
                    _sheet_update_deploy(pr_id, status, final_date)
                    return
            except Exception:
                pass
    threading.Thread(target=_run, daemon=True).start()


@app.route("/api/pr/<int:pr_id>/complete", methods=["POST"])
def complete(pr_id):
    try:
        state = load_state()
        completed_notified = state.setdefault("completed_notified", [])
        result = subprocess.run([
            "az", "repos", "pr", "update", "--id", str(pr_id),
            "--status", "completed", "--org", ORG_URL, "-o", "json"
        ], capture_output=True, text=True)
        if result.returncode != 0:
            return jsonify({"ok": False, "error": result.stderr or result.stdout}), 500
        pr_data = json.loads(result.stdout) if result.stdout.strip().startswith("{") else {}
        author = pr_data.get("createdBy", {}).get("displayName", "")
        blocked_authors = [a.lower().strip() for a in load_blocked_authors()]
        is_blocked = author.lower().strip() in blocked_authors
        if not is_blocked and pr_id not in completed_notified:
            notify_pr_slack(pr_id, "complete")
            completed_notified.append(pr_id)
            save_state(state)
        # Iniciar polling de despliegue en background
        merge_commit  = pr_data.get("lastMergeCommit", {}).get("commitId")
        closed_date   = pr_data.get("closedDate", "")
        target_branch = pr_data.get("targetRefName", "")
        _poll_deploy_background(pr_id, merge_commit, closed_date, target_branch, author=author)
        # Registrar PR en Google Sheet
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
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/pr/<int:pr_id>/notify-deploy", methods=["POST"])
def notify_deploy(pr_id):
    try:
        state = load_state()
        deploy_notified = state.setdefault("deploy_notified", [])
        if pr_id in deploy_notified:
            return jsonify({"ok": True})
        data   = request.get_json(silent=True) or {}
        status = data.get("status", "")
        text   = "✅ Despliegue completado" if status == "succeeded" else "❌ Despliegue fallido"
        thread_ts = find_pr_thread(pr_id, save_if_found=True)
        if not thread_ts:
            return jsonify({"ok": False, "error": f"No se encontró el hilo del PR {pr_id}"}), 404
        slack_api("chat.postMessage", {"channel": SLACK_PR_CHANNEL, "text": text, "thread_ts": thread_ts})
        deploy_notified.append(pr_id)
        save_state(state)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/pr/<int:pr_id>/deploy-status")
def deploy_status(pr_id):
    merge_commit  = request.args.get("mergeCommit", "")
    closed_date   = request.args.get("closedDate", "")
    target_branch = request.args.get("target", "")
    status, _ = get_deploy_status(pr_id, merge_commit, closed_date, target_branch)
    return jsonify({"ok": True, "status": status})


@app.route("/api/pr/<int:pr_id>/request-ta-approval", methods=["POST"])
def request_ta_approval(pr_id):
    import time
    try:
        state = load_state()
        ta_notified = state.setdefault("ta_notified", [])
        if pr_id in ta_notified:
            return jsonify({"ok": True, "already_notified": True})
        thread_ts = wait_for_pr_thread(pr_id)
        time.sleep(5)
        mentions = get_pr_ta_reviewers(pr_id) or ["TA Reviewer"]
        slack_api("chat.postMessage", {
            "channel": SLACK_PR_CHANNEL, "thread_ts": thread_ts,
            "text": f"{' '.join(mentions)} TA por favor revisa este PR"
        })
        ta_notified.append(pr_id)
        save_state(state)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/config/auto-approve", methods=["GET"])
def get_auto_approve_config():
    return jsonify(load_auto_approve_config())

@app.route("/api/config/auto-approve", methods=["POST"])
def set_auto_approve_config():
    data = request.get_json(silent=True) or {}
    cfg = load_auto_approve_config()
    if "enabled" in data:
        cfg["enabled"] = bool(data["enabled"])
    if "branches" in data:
        cfg["branches"] = list(data["branches"])
    save_auto_approve_config(cfg)
    return jsonify({"ok": True, "config": cfg})


@app.route("/api/config/blocked-authors", methods=["GET"])
def get_blocked_authors():
    return jsonify(load_blocked_authors())

@app.route("/api/config/blocked-authors", methods=["POST"])
def set_blocked_authors():
    data = request.get_json(silent=True) or {}
    authors = list(data.get("authors", []))
    save_blocked_authors(authors)
    return jsonify({"ok": True, "authors": authors})


@app.route("/api/stats")
def api_stats():
    try:
        from datetime import datetime, timezone, timedelta
        today = datetime.now(timezone.utc).date().isoformat()
        yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()

        # PRs activos
        active_prs = get_prs()
        active_count = len(active_prs)
        conflicts_count = sum(1 for p in active_prs if p.get("hasConflicts"))
        auto_approved_active = sum(1 for p in active_prs if p.get("myVote") == "approved")

        # PRs completados hoy
        completed_today = prs_completed_by_date(today, today)
        completed_count = len(completed_today)

        # PRs completados ayer (para comparar tendencia)
        completed_yesterday = prs_completed_by_date(yesterday, yesterday)
        yesterday_count = len(completed_yesterday)

        # Tiempo promedio de revisión (de los completados hoy, usando creationDate → closedDate)
        review_times = []
        for pr in completed_today:
            t = _minutes_between(pr.get("creationDate", ""), pr.get("closedDate", ""))
            if isinstance(t, (int, float)) and t > 0:
                review_times.append(t)
        avg_review_min = round(sum(review_times) / len(review_times)) if review_times else 0

        # Tasa de auto-aprobación (del estado guardado)
        state = load_state()
        auto_approved_ids = set(state.get("auto_approved", []))
        auto_rate = 0
        if completed_count > 0:
            auto_in_today = sum(1 for pr in completed_today if pr["id"] in auto_approved_ids)
            auto_rate = round(auto_in_today / completed_count * 100)

        # Tendencia: diferencia de completados hoy vs ayer
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
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/prs/export-sheets", methods=["POST"])
def export_sheets():
    try:
        data = request.get_json(silent=True) or {}
        date_from = data.get("from", "")
        date_to   = data.get("to", "")
        if not date_from or not date_to:
            from datetime import datetime, timezone
            today = datetime.now(timezone.utc).date().isoformat()
            date_from = date_to = today

        prs = prs_completed_by_date(date_from, date_to)
        state = load_state()
        auto_approved_ids = set(state.get("auto_approved", []))
        blocked_authors = [a.lower().strip() for a in load_blocked_authors()]
        token = get_token()

        rows = [SHEET_HEADERS]
        for pr in prs:
            pr_id = pr["id"]

            # Marcar bloqueado
            pr["blocked"] = (pr.get("createdBy") or "").lower().strip() in blocked_authors

            # Obtener policy status para PRs completados
            try:
                pr["policyStatus"] = get_pr_policy_status(pr_id, token)
            except Exception:
                pr["policyStatus"] = ""

            # Obtener fecha de aprobación: buscar el reviewer con vote=10 y fecha más temprana
            approval_date = ""
            for reviewer in pr.get("reviewers", []):
                if reviewer.get("vote", 0) == 10:
                    # Azure no devuelve la fecha del voto en el listado,
                    # usamos la fecha de cierre como aproximación si no hay otra fuente
                    pass
            # Intentar obtener fecha real de aprobación via threads
            approval_date = _get_approval_date(pr_id, token)
            # Fallback: si no encontramos fecha de aprobación, usar closedDate
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

        svc = _sheets_service()
        sheet = svc.spreadsheets()

        # Limpiar hoja y escribir desde A1
        sheet.values().clear(spreadsheetId=SHEET_ID, range="Hoja 1").execute()
        sheet.values().update(
            spreadsheetId=SHEET_ID,
            range="Hoja 1!A1",
            valueInputOption="RAW",
            body={"values": rows},
        ).execute()

        return jsonify({"ok": True, "rows": len(rows) - 1})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)
