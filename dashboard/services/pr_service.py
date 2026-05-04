import logging
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
from check_salesforce_prs import classify, fetch_changes, normalize_ref, get_my_vote

from integrations.azure import (
    ORG_URL, PROJECT, REPOSITORY, check_token, get_pr_policy_status,
    get_pr_ta_reviewers, list_active_prs, set_pr_vote, TokenExpiredError
)
from integrations.slack import (
    SLACK_PR_CHANNEL, find_pr_thread, slack_api, wait_for_pr_thread
)
from integrations.state import (
    load_auto_approve_config, load_blocked_authors, load_blocked_branches,
    load_state, save_state
)

logger = logging.getLogger("pr_dashboard")

_prs_cache = {"data": None, "ts": 0.0, "error": None, "refreshing": False}
_prs_cache_lock = threading.Lock()
_PRS_TTL = 30


def invalidate_prs_cache():
    with _prs_cache_lock:
        _prs_cache["ts"] = 0.0


def get_prs():
    with _prs_cache_lock:
        cached = _prs_cache["data"]
        age = time.time() - _prs_cache["ts"]
        error = _prs_cache["error"]
        refreshing = _prs_cache["refreshing"]

    if error == "TOKEN_EXPIRED":
        raise TokenExpiredError("Token de Azure expirado")

    if cached is not None:
        if age > _PRS_TTL and not refreshing:
            with _prs_cache_lock:
                _prs_cache["refreshing"] = True
            threading.Thread(target=_refresh_background, daemon=True).start()
        return cached

    with _prs_cache_lock:
        if not _prs_cache["refreshing"]:
            _prs_cache["refreshing"] = True
    result = _fetch_prs()
    with _prs_cache_lock:
        _prs_cache["data"] = result
        _prs_cache["ts"] = time.time()
        _prs_cache["refreshing"] = False
    return result


def _refresh_background():
    try:
        fresh = _fetch_prs()
        with _prs_cache_lock:
            _prs_cache["data"] = fresh
            _prs_cache["ts"] = time.time()
            _prs_cache["error"] = None
    except TokenExpiredError:
        with _prs_cache_lock:
            _prs_cache["error"] = "TOKEN_EXPIRED"
    except Exception as e:
        logger.error("[prs-cache] Error refrescando: %s", e)
        with _prs_cache_lock:
            _prs_cache["error"] = str(e)
    finally:
        with _prs_cache_lock:
            _prs_cache["refreshing"] = False


def _fetch_prs():
    try:
        token = check_token()
    except TokenExpiredError:
        raise

    try:
        prs = list_active_prs()
    except Exception as e:
        err = str(e)
        if "AADSTS" in err or "az login" in err or "token" in err.lower():
            raise TokenExpiredError("Token de Azure expirado")
        raise

    prs = [pr for pr in prs if normalize_ref(pr.get("targetRefName", "")) in {"develop", "develop-pr", "releaseproyecto/r6"}]

    state = load_state()
    blocked_authors = [a.lower().strip() for a in load_blocked_authors()]
    blocked_branches = [b.lower().strip() for b in load_blocked_branches()]

    def _collect(pr):
        pr_id = str(pr["pullRequestId"])
        source_branch = normalize_ref(pr.get("sourceRefName", "")).lower().strip()
        target_branch = normalize_ref(pr.get("targetRefName", "")).lower().strip()
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

    with ThreadPoolExecutor(max_workers=8) as executor:
        collected = [r for r in (f.result() for f in as_completed(
            {executor.submit(_collect, pr): pr for pr in prs}
        )) if r is not None]

    auto_cfg = load_auto_approve_config()
    reports = []

    for report in collected:
        pr_id = str(report["id"])
        policy_status = report["policyStatus"]

        # Conflictos
        if report["hasConflicts"]:
            report["verdict"] = "resolver conflicto"
            _notify_once(state, "conflicts_notified", int(pr_id), lambda pid=pr_id: _notify_conflict(pid))

        # Policy failed
        elif policy_status == "failed":
            report["verdict"] = "evaluar check"
            _notify_once(state, "check_notified", int(pr_id), lambda pid=pr_id: _notify_check(pid))

        elif policy_status == "running" and report["verdict"] not in ("rechazar", "revisar") and report["myVote"] != "approved":
            report["verdict"] = "posible aprobación"

        if (report["myVote"] == "approved" and not report["canComplete"]
                and not report["hasConflicts"] and policy_status not in ("failed",)):
            report["verdict"] = "TA Reviewer"

        target_branch = normalize_ref(report.pop("_targetRefName", ""))

        # Auto-aprobación
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
            _try_auto_approve(pr_id, report, state, token)

        # Auto-complete
        if (
            target_branch in {"develop", "develop-pr", "releaseproyecto/r6"}
            and report["myVote"] == "approved"
            and report["canComplete"]
            and not report["hasConflicts"]
            and not report["blocked"]
            and not report["frozen"]
        ):
            _try_auto_complete(pr_id, report, state, token)

        reports.append(report)

    save_state(state)
    priority = {"rechazar": 0, "revisar": 1, "aprobable con cautela": 2, "aprobable": 3}
    return sorted(reports, key=lambda x: (1 if x.get("blocked") else 0, priority.get(x["verdict"], 9), x["id"]))


def _notify_once(state, key, pr_id, fn):
    notified = state.setdefault(key, [])
    if pr_id not in notified:
        notified.append(pr_id)
        save_state(state)
        threading.Thread(target=fn, daemon=True).start()


def _try_auto_complete(pr_id, report, state, token):
    from integrations.azure import complete_pr, get_pr_approval_date, get_pr_policy_status
    from services.deploy_service import poll_deploy_background
    from services.sheets_service import append_pr

    auto_completed = state.setdefault("auto_completed", [])
    if int(pr_id) in auto_completed:
        return
    result = complete_pr(pr_id)
    if result.returncode != 0:
        logger.warning("[auto-complete] Falló PR %s: %s", pr_id, result.stderr or result.stdout)
        return
    logger.info("[auto-complete] PR %s completado automáticamente", pr_id)
    auto_completed.append(int(pr_id))

    import json
    pr_data = {}
    if result.stdout.strip().startswith("{"):
        try:
            pr_data = json.loads(result.stdout)
        except Exception:
            pass

    merge_commit  = (pr_data.get("lastMergeCommit") or {}).get("commitId")
    closed_date   = pr_data.get("closedDate", "")
    target_branch = pr_data.get("targetRefName", "")
    author        = (pr_data.get("createdBy") or {}).get("displayName", "")

    poll_deploy_background(pr_id, merge_commit, closed_date, target_branch, author=author)

    approval_date = get_pr_approval_date(pr_id, token)
    policy_status = get_pr_policy_status(pr_id, token)
    sheet_pr = {
        "pullRequestId": pr_id,
        "title": pr_data.get("title", report.get("title", "")),
        "createdBy": author or report.get("createdBy", ""),
        "targetRefName": target_branch,
        "creationDate": pr_data.get("creationDate", report.get("creationDate", "")),
        "closedDate": closed_date,
        "hasConflicts": pr_data.get("mergeStatus") == "conflicts",
        "policyStatus": policy_status,
    }
    append_pr(sheet_pr, auto_approved=int(pr_id) in state.get("auto_approved", []), approval_date=approval_date)

    # Notificar solo si no se ha notificado antes
    completed_notified = state.setdefault("completed_notified", [])
    if int(pr_id) not in completed_notified:
        def _notify():
            thread_ts = wait_for_pr_thread(int(pr_id))
            if thread_ts:
                try:
                    slack_api("chat.postMessage", {
                        "channel": SLACK_PR_CHANNEL,
                        "thread_ts": thread_ts,
                        "text": "🚀 PR integrado — si no hay conflicto el despliegue estará en curso, te avisamos cuando termine.",
                    })
                    # Marcar como notificado después de enviar exitosamente
                    state_inner = load_state()
                    completed_notified_inner = state_inner.setdefault("completed_notified", [])
                    if int(pr_id) not in completed_notified_inner:
                        completed_notified_inner.append(int(pr_id))
                        save_state(state_inner)
                except Exception as e:
                    logger.error("[auto-complete] Slack PR %s: %s", pr_id, e)

        threading.Thread(target=_notify, daemon=True).start()


def _notify_conflict(pr_id):
    try:
        thread_ts = wait_for_pr_thread(int(pr_id))
        if thread_ts:
            slack_api("chat.postMessage", {"channel": SLACK_PR_CHANNEL, "thread_ts": thread_ts, "text": "⚠️ ¡Por favor resolver conflicto!"})
    except Exception:
        pass


def _notify_check(pr_id):
    try:
        thread_ts = wait_for_pr_thread(int(pr_id))
        if thread_ts:
            slack_api("chat.postMessage", {"channel": SLACK_PR_CHANNEL, "thread_ts": thread_ts, "text": "🔍 Por favor verifica el check del Pull Request"})
    except Exception:
        pass


def _try_auto_approve(pr_id, report, state, token):
    auto_approved = state.setdefault("auto_approved", [])
    if int(pr_id) in auto_approved and report["myVote"] == "approved":
        return
    if int(pr_id) in auto_approved:
        auto_approved.remove(int(pr_id))
    result = set_pr_vote(pr_id, "approve")
    if result.returncode == 0:
        logger.info("[auto-approve] PR %s aprobado", pr_id)
        auto_approved.append(int(pr_id))
        report["myVote"] = "approved"
        report["canComplete"] = True

        def _notify():
            thread_ts = wait_for_pr_thread(int(pr_id))
            if not thread_ts:
                return
            try:
                slack_api("chat.postMessage", {"channel": SLACK_PR_CHANNEL, "thread_ts": thread_ts, "text": "✅ Aprobado"})
            except Exception as e:
                logger.error("[auto-approve] Slack PR %s: %s", pr_id, e)
            ta_notified = state.setdefault("ta_notified", [])
            if int(pr_id) not in ta_notified:
                try:
                    mentions = get_pr_ta_reviewers(int(pr_id), token)
                    text = f"{' '.join(mentions)} TA por favor revisa este PR" if mentions else "TA por favor revisa este PR"
                    slack_api("chat.postMessage", {"channel": SLACK_PR_CHANNEL, "thread_ts": thread_ts, "text": text})
                    ta_notified.append(int(pr_id))
                    save_state(state)
                except Exception as te:
                    logger.error("[auto-approve] TA PR %s: %s", pr_id, te)

        threading.Thread(target=_notify, daemon=True).start()
    else:
        logger.warning("[auto-approve] Falló vote PR %s: %s", pr_id, result.stderr or result.stdout)
