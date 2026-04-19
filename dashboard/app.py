#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen
from flask import Flask, jsonify, render_template, request

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from check_salesforce_prs import (
    classify, fetch_changes, get_token, normalize_ref,
    load_state, save_state, get_my_vote
)

ORG_URL = "https://dev.azure.com/OrgClaroColombia"
PROJECT = "SalesForce"
REPOSITORY = "SalesForce"
PIPELINE_ID = 3840
SLACK_PR_CHANNEL = "C080K9D6EG2"

AUTO_APPROVE_CONFIG_PATH = Path(__file__).parent.parent / "memoria" / "auto_approve_config.json"

def load_auto_approve_config():
    if AUTO_APPROVE_CONFIG_PATH.exists():
        return json.loads(AUTO_APPROVE_CONFIG_PATH.read_text())
    return {"enabled": False, "branches": []}

def save_auto_approve_config(cfg):
    AUTO_APPROVE_CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))

TA_SLACK_IDS = {
    "gustavo alonso muciño": "U06JUHG1G9Y",
    "hugo revuelta":         "U07TQ8JNMBR",
    "gabriel alvis":         "U066X49C5NZ",
    "francisco zubizarreta": "U01LXV1UD3K",
    "luís guilherme lino":   "U023L6SJVQW",
    "luis guilherme lino":   "U023L6SJVQW",
}

SLACK_TOKEN = None

def _load_env():
    global SLACK_TOKEN
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("SLACK_TOKEN="):
                SLACK_TOKEN = line.split("=", 1)[1].strip()

_load_env()

app = Flask(__name__)


def run(cmd):
    return subprocess.check_output(cmd, text=True)


def slack_api(method, payload):
    data = json.dumps(payload).encode()
    req = Request(
        f"https://slack.com/api/{method}",
        data=data,
        headers={"Authorization": f"Bearer {SLACK_TOKEN}", "Content-Type": "application/json"},
    )
    with urlopen(req, timeout=10) as r:
        return json.loads(r.read())


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


def wait_for_pr_thread(pr_id, interval=15):
    import time
    while True:
        ts = find_pr_thread(pr_id, save_if_found=True)
        if ts:
            return ts
        time.sleep(interval)


def notify_pr_slack(pr_id, action):
    labels = {"approve": "✅ Aprobado", "reject": "❌ Rechazado", "complete": "🚀 PR integrado — si no hay conflicto el despliegue estará en curso, te avisamos cuando termine."}
    text = labels.get(action, action)
    thread_ts = wait_for_pr_thread(pr_id) if action == "approve" else find_pr_thread(pr_id, save_if_found=True)
    payload = {"channel": SLACK_PR_CHANNEL, "text": text}
    if thread_ts:
        payload["thread_ts"] = thread_ts
    slack_api("chat.postMessage", payload)


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
    """Busca el release asociado al PR via commit de merge o branch del PR."""
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
        return "unknown"
    except Exception:
        return "unknown"


def _api_azure(url, token):
    req = Request(url, headers={"Authorization": f"Bearer {token}"})
    with urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def _release_status(release):
    envs = release.get("environments", [])
    if not envs:
        return "unknown"
    
    statuses = [e.get("status", "") for e in envs]
    
    # Si alguno está en progreso, el release está en progreso
    if any(s == "inProgress" for s in statuses):
        return "inProgress"
    
    # Si alguno está pendiente (notStarted, queued), el release aún no termina
    if any(s in ("notStarted", "queued") for s in statuses):
        return "inProgress"
    
    # Si alguno falló o fue rechazado, el release falló
    if any(s in ("rejected", "failed", "canceled") for s in statuses):
        return "failed"
    
    # Solo si TODOS están en estado final exitoso (succeeded o skipped)
    if all(s in ("succeeded", "skipped") for s in statuses):
        return "succeeded"
    
    return "inProgress"


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
    reports = []
    for pr in prs:
        pr_id = str(pr["pullRequestId"])
        changes = fetch_changes(pr_id, token)
        report = classify(pr, changes)
        report["creationDate"] = pr.get("creationDate", "")
        report["url"] = f"{ORG_URL}/{PROJECT}/_git/{REPOSITORY}/pullrequest/{pr_id}"
        report["myVote"] = get_my_vote(pr)
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
        if report["myVote"] == "approved" and not report["canComplete"] and not report["hasConflicts"]:
            report["verdict"] = "TA Reviewer"

        # Auto-aprobación
        auto_cfg = load_auto_approve_config()
        target_branch = normalize_ref(pr.get("targetRefName", ""))
        if (
            auto_cfg.get("enabled")
            and target_branch in auto_cfg.get("branches", [])
            and not report["hasConflicts"]
            and policy_status != "failed"
            and report["verdict"] in ("aprobable", "aprobable con cautela", "posible aprobación")
            and not report["reasons"]
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
                            mentions = get_pr_ta_reviewers(int(pr_id)) or ["TA Reviewer"]
                            if thread_ts:
                                slack_api("chat.postMessage", {
                                    "channel": SLACK_PR_CHANNEL,
                                    "thread_ts": thread_ts,
                                    "text": f"{' '.join(mentions)} por favor revisa este PR 🙏"
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
            "mergeCommit": p.get("lastMergeCommit", {}).get("commitId", ""),
            "url": f"{ORG_URL}/{PROJECT}/_git/{REPOSITORY}/pullrequest/{p['pullRequestId']}",
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
        return jsonify({"ok": True})
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
        notify_pr_slack(pr_id, "reject")
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


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
        if pr_id not in completed_notified:
            notify_pr_slack(pr_id, "complete")
            completed_notified.append(pr_id)
            save_state(state)
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
        payload = {"channel": SLACK_PR_CHANNEL, "text": text}
        if thread_ts:
            payload["thread_ts"] = thread_ts
        else:
            return jsonify({"ok": False, "error": f"No se encontró el hilo del PR {pr_id}"}), 404
        slack_api("chat.postMessage", payload)
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
    return jsonify({"ok": True, "status": get_deploy_status(pr_id, merge_commit, closed_date, target_branch)})


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
            "text": f"{' '.join(mentions)} por favor revisa este PR 🙏"
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


if __name__ == "__main__":
    app.run(debug=True, port=5000)
