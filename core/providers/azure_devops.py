import json
import subprocess
from urllib.parse import quote
from urllib.request import Request, urlopen

from core.providers.base import PRProvider, PR, DeployStatus


def _run(cmd):
    return subprocess.check_output(cmd, text=True)


def _get_token():
    return _run([
        "az", "account", "get-access-token",
        "--resource", "499b84ac-1321-427f-aa17-267ca6975798",
        "--query", "accessToken", "-o", "tsv",
    ]).strip()


def _normalize_ref(ref):
    return (ref or "").replace("refs/heads/", "")


def _api(url, token):
    req = Request(url, headers={"Authorization": f"Bearer {token}"})
    with urlopen(req, timeout=15) as r:
        return json.loads(r.read())


class AzureDevOpsProvider(PRProvider):

    def __init__(self, config):
        self.org_url    = config.org_url
        self.project    = config.project
        self.repository = config.repository
        self.extra      = config.extra or {}
        # Clasificador opcional (Salesforce-specific) — se inyecta desde fuera si se necesita
        self._classifier = self.extra.get("classifier")

    def _token(self):
        return _get_token()

    def get_active_prs(self) -> list[PR]:
        token = self._token()
        raw = json.loads(_run([
            "az", "repos", "pr", "list", "--status", "active",
            "--repository", self.repository,
            "--org", self.org_url,
            "--project", self.project,
            "-o", "json",
        ]))
        watched = set(self.extra.get("watched_branches", []))
        if watched:
            raw = [p for p in raw if _normalize_ref(p.get("targetRefName", "")) in watched]

        result = []
        for p in raw:
            pr_id = str(p["pullRequestId"])
            policy_status = self._policy_status(pr_id, token)
            result.append(PR(
                id=int(pr_id),
                title=p.get("title", ""),
                source=_normalize_ref(p.get("sourceRefName", "")),
                target=_normalize_ref(p.get("targetRefName", "")),
                created_by=(p.get("createdBy") or {}).get("displayName", ""),
                url=f"{self.org_url}/{self.project}/_git/{self.repository}/pullrequest/{pr_id}",
                creation_date=p.get("creationDate", ""),
                my_vote=self._my_vote(p),
                has_conflicts=p.get("mergeStatus") == "conflicts",
                can_complete=policy_status == "approved",
                policy_status=policy_status,
                reviewers=[
                    {"name": (r.get("displayName") or ""), "vote": r.get("vote", 0)}
                    for r in p.get("reviewers", [])
                ],
            ))
        return result

    def get_completed_prs(self, date_from: str, date_to: str) -> list[PR]:
        raw = json.loads(_run([
            "az", "repos", "pr", "list", "--status", "completed",
            "--repository", self.repository,
            "--org", self.org_url,
            "--project", self.project,
            "-o", "json",
        ]))
        return [
            PR(
                id=p["pullRequestId"],
                title=p.get("title", ""),
                source=_normalize_ref(p.get("sourceRefName", "")),
                target=_normalize_ref(p.get("targetRefName", "")),
                created_by=(p.get("createdBy") or {}).get("displayName", ""),
                url=f"{self.org_url}/{self.project}/_git/{self.repository}/pullrequest/{p['pullRequestId']}",
                creation_date=p.get("creationDate", ""),
                closed_date=p.get("closedDate", ""),
            )
            for p in raw if date_from <= p.get("closedDate", "")[:10] <= date_to
        ]

    def approve(self, pr_id: int) -> None:
        result = subprocess.run([
            "az", "repos", "pr", "set-vote", "--id", str(pr_id),
            "--vote", "approve", "--org", self.org_url, "-o", "json"
        ], capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(result.stderr or result.stdout)

    def reject(self, pr_id: int, comment: str) -> None:
        result = subprocess.run([
            "az", "repos", "pr", "set-vote", "--id", str(pr_id),
            "--vote", "reject", "--org", self.org_url, "-o", "json"
        ], capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(result.stderr or result.stdout)
        subprocess.run([
            "az", "repos", "pr", "comment", "add", "--id", str(pr_id),
            "--comment", comment, "--org", self.org_url,
            "--project", self.project, "-o", "none"
        ])

    def complete(self, pr_id: int) -> None:
        result = subprocess.run([
            "az", "repos", "pr", "update", "--id", str(pr_id),
            "--status", "completed", "--org", self.org_url, "-o", "json"
        ], capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(result.stderr or result.stdout)

    def get_deploy_status(self, pr: PR) -> DeployStatus:
        try:
            token = self._token()
            org_name = self.org_url.rstrip("/").split("/")[-1]
            vsrm = f"https://vsrm.dev.azure.com/{org_name}/{self.project}"
            releases = _api(f"{vsrm}/_apis/release/releases?api-version=7.1&$top=50", token).get("value", [])
            pr_branch = f"refs/pull/{pr.id}/merge"
            for rel in releases:
                detail = _api(f"{vsrm}/_apis/release/releases/{rel['id']}?api-version=7.1", token)
                for art in detail.get("artifacts", []):
                    branch = art.get("definitionReference", {}).get("branch", {}).get("id", "")
                    if branch == pr_branch:
                        return DeployStatus(status=self._release_status(detail))
                    if pr.closed_date and branch == f"refs/heads/{pr.target}":
                        if rel.get("createdOn", "") >= pr.closed_date:
                            return DeployStatus(status=self._release_status(detail))
            return DeployStatus(status="unknown")
        except Exception:
            return DeployStatus(status="unknown")

    # ── helpers ──────────────────────────────────────────────────────────────

    def _my_vote(self, pr: dict):
        try:
            me = _run(["az", "account", "show", "--query", "user.name", "-o", "tsv"]).strip().lower()
        except Exception:
            return None
        for r in pr.get("reviewers", []):
            name = (r.get("uniqueName") or r.get("displayName") or "").lower()
            if name == me:
                v = r.get("vote", 0)
                if v == 10:  return "approved"
                if v == -10: return "rejected"
        return None

    def _policy_status(self, pr_id: str, token: str) -> str:
        try:
            project_id = _run([
                "az", "devops", "project", "show",
                "--project", self.project, "--org", self.org_url,
                "--query", "id", "-o", "tsv"
            ]).strip()
            artifact_id = f"vstfs:///CodeReview/CodeReviewId/{project_id}/{pr_id}"
            url = (f"{self.org_url}/{self.project}/_apis/policy/evaluations"
                   f"?artifactId={quote(artifact_id, safe='')}&api-version=7.1-preview.1")
            data = _api(url, token)
            statuses = [e.get("status") for e in data.get("value", [])]
            if not statuses:            return "unknown"
            if any(s == "rejected"  for s in statuses): return "failed"
            if any(s in ("queued", "running") for s in statuses): return "running"
            if all(s == "approved"  for s in statuses): return "approved"
            return "unknown"
        except Exception:
            return "unknown"

    @staticmethod
    def _release_status(release: dict) -> str:
        statuses = [e.get("status", "") for e in release.get("environments", [])]
        if any(s == "inProgress" for s in statuses): return "inProgress"
        if any(s == "rejected"   for s in statuses): return "failed"
        if any(s == "succeeded"  for s in statuses): return "succeeded"
        return "inProgress"
