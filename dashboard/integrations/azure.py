import json
import logging
import os
import subprocess
import threading
import time
from urllib.request import Request, urlopen

from utils import retry


def normalize_ref(ref):
    return ref.replace("refs/heads/", "") if ref else ref

logger = logging.getLogger("pr_dashboard")

# ── Configuración dinámica por tenant ─────────────────────────────────────────

def _get_azure_config():
    """Obtiene la configuración de Azure DevOps del tenant actual."""
    from integrations.tenant_context import get_current_tenant
    
    tenant = get_current_tenant()
    if tenant:
        try:
            return tenant.azure_config
        except Exception as e:
            logger.warning(f"Error obteniendo config de Azure del tenant: {e}")
    
    # Fallback a variables de entorno (para compatibilidad)
    org = os.getenv("AZURE_ORG", "salesforce-mx")
    return {
        'org_url': f"https://dev.azure.com/{org}",
        'project': os.getenv("AZURE_PROJECT", "SalesForce"),
        'repository': os.getenv("AZURE_REPOSITORY", "SalesForce"),
        'pat_token': None
    }


# Funciones para obtener configuración dinámica
def get_org_url():
    return _get_azure_config()['org_url']

def get_project():
    return _get_azure_config()['project']

def get_repository():
    return _get_azure_config()['repository']

# Para compatibilidad con código existente que usa las constantes
# Estas ahora son funciones que se llaman dinámicamente
ORG_URL = get_org_url()
PROJECT = get_project()
REPOSITORY = get_repository()

# ── Token cache ───────────────────────────────────────────────────────────────
_token_cache = {"value": None, "expires_at": 0.0}
_token_lock = threading.Lock()

# ── Project ID cache ──────────────────────────────────────────────────────────
_project_id_cache = None


class TokenExpiredError(Exception):
    pass


def get_token():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
    from check_salesforce_prs import get_token as _get_token
    return _get_token()


def check_token():
    with _token_lock:
        if time.time() < _token_cache["expires_at"]:
            return _token_cache["value"]
    try:
        token = get_token()
        if not token:
            raise TokenExpiredError("Token de Azure expirado")
        with _token_lock:
            _token_cache["value"] = token
            _token_cache["expires_at"] = time.time() + 3300
        return token
    except TokenExpiredError:
        raise
    except Exception as e:
        err = str(e)
        if "AADSTS" in err or "Please run" in err or "az login" in err or "token" in err.lower():
            with _token_lock:
                _token_cache["value"] = None
                _token_cache["expires_at"] = 0.0
            raise TokenExpiredError("Token de Azure expirado")
        raise


def invalidate_token():
    with _token_lock:
        _token_cache["value"] = None
        _token_cache["expires_at"] = 0.0


def api_azure(url, token):
    def _call():
        req = Request(url, headers={"Authorization": f"Bearer {token}"})
        with urlopen(req, timeout=5) as r:
            return json.loads(r.read())
    return retry(_call, retries=2, label="azure_api")


def list_active_prs():
    return json.loads(subprocess.check_output([
        "az", "repos", "pr", "list", "--status", "active",
        "--repository", get_repository(), "--org", get_org_url(), "--project", get_project(), "-o", "json",
    ], text=True))


def list_completed_prs(top=100):
    return json.loads(subprocess.check_output([
        "az", "repos", "pr", "list", "--status", "completed",
        "--repository", REPOSITORY, "--org", ORG_URL, "--project", PROJECT,
        "--top", str(top), "-o", "json",
    ], text=True))


def set_pr_vote(pr_id, vote):
    """vote: 'approve' | 'reject'"""
    return subprocess.run([
        "az", "repos", "pr", "set-vote", "--id", str(pr_id),
        "--vote", vote, "--org", ORG_URL, "-o", "json"
    ], capture_output=True, text=True)


def complete_pr(pr_id):
    return subprocess.run([
        "az", "repos", "pr", "update", "--id", str(pr_id),
        "--status", "completed", "--org", ORG_URL, "-o", "json"
    ], capture_output=True, text=True)


def add_pr_comment(pr_id, comment):
    subprocess.run([
        "az", "repos", "pr", "comment", "add", "--id", str(pr_id),
        "--comment", comment, "--org", ORG_URL, "--project", PROJECT, "-o", "none"
    ])


def get_pr_reviewers(pr_id, token):
    url = (f"{ORG_URL}/{PROJECT}/_apis/git/repositories/{REPOSITORY}"
           f"/pullRequests/{pr_id}/reviewers?api-version=7.1")
    return api_azure(url, token).get("value", [])


def get_pr_threads(pr_id, token):
    url = (f"{ORG_URL}/{PROJECT}/_apis/git/repositories/{REPOSITORY}"
           f"/pullRequests/{pr_id}/threads?api-version=7.1")
    return api_azure(url, token).get("value", [])


def get_pr_by_id(pr_id, token):
    """Obtiene un PR específico por ID — evita listar todos los PRs."""
    url = (f"{ORG_URL}/{PROJECT}/_apis/git/repositories/{REPOSITORY}"
           f"/pullRequests/{pr_id}?api-version=7.1")
    return api_azure(url, token)


def get_policy_evaluations(pr_id, token):
    global _project_id_cache
    if _project_id_cache is None:
        _project_id_cache = subprocess.check_output([
            "az", "devops", "project", "show",
            "--project", PROJECT, "--org", ORG_URL, "--query", "id", "-o", "tsv"
        ], text=True).strip()
    from urllib.parse import quote
    artifact_id = f"vstfs:///CodeReview/CodeReviewId/{_project_id_cache}/{pr_id}"
    url = (f"{ORG_URL}/{PROJECT}/_apis/policy/evaluations"
           f"?artifactId={quote(artifact_id, safe='')}&api-version=7.1-preview.1")
    return api_azure(url, token).get("value", [])


def get_pr_policy_status(pr_id, token):
    try:
        evals = get_policy_evaluations(pr_id, token)
        statuses = [e.get("status") for e in evals]
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


def get_pr_approval_date(pr_id, token):
    try:
        threads = get_pr_threads(pr_id, token)
        dates = []
        for t in threads:
            for c in t.get("comments", []):
                if c.get("commentType") == "system" and "approved" in (c.get("content") or "").lower():
                    d = c.get("publishedDate") or c.get("lastUpdatedDate")
                    if d:
                        dates.append(d)
        return min(dates) if dates else ""
    except Exception:
        return ""


def get_pr_ta_reviewers(pr_id, token, only_pending=True):
    """Obtiene reviewers TA del PR consultando directamente por ID."""
    from integrations.slack import TA_SLACK_IDS
    try:
        reviewers = get_pr_reviewers(pr_id, token)
        mentions = []
        for r in reviewers:
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
