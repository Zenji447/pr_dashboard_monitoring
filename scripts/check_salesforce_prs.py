#!/usr/bin/env python3
import json
import re
import subprocess
from pathlib import Path
from urllib.request import Request, urlopen

ORG = "OrgClaroColombia"
ORG_URL = f"https://dev.azure.com/{ORG}"
PROJECT = "SalesForce"
REPOSITORY = "SalesForce"
REPO_ID = "60023994-6817-4143-876a-928748a09628"
LOCAL_REPO = "/home/zen6/cc/SalesForce"
STATE_PATH = Path("/home/zen6/.openclaw/workspace/state/salesforce-pr-watch.json")


def run(cmd):
    return subprocess.check_output(cmd, text=True)


def get_token():
    return run([
        "az", "account", "get-access-token",
        "--resource", "499b84ac-1321-427f-aa17-267ca6975798",
        "--query", "accessToken",
        "-o", "tsv",
    ]).strip()


def api_json(path, token):
    url = f"{ORG_URL}/{PROJECT}/_apis/git/repositories/{REPO_ID}{path}"
    req = Request(url, headers={"Authorization": f"Bearer {token}"})
    with urlopen(req, timeout=8) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def git_lines(args):
    try:
        out = run(["git", "-C", LOCAL_REPO] + args)
        return out.splitlines()
    except Exception:
        return []


def normalize_ref(ref):
    return ref.replace("refs/heads/", "") if ref else ref


def get_my_vote(pr):
    """Retorna 'approved', 'rejected' o None según el voto del usuario actual."""
    try:
        me = run(["az", "account", "show", "--query", "user.name", "-o", "tsv"]).strip().lower()
    except Exception:
        return None
    for reviewer in pr.get("reviewers", []):
        name = (reviewer.get("uniqueName") or reviewer.get("displayName") or "").lower()
        if name == me:
            vote = reviewer.get("vote", 0)
            if vote == 10:
                return "approved"
            if vote == -10:
                return "rejected"
    return None



    return ref.replace("refs/heads/", "") if ref else ref


def load_state():
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"seen": {}}


def save_state(state):
    STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def title_has_work_item(title):
    return bool(re.search(r"\b(?:BUG|HDU|HU)?\s*-?\s*\d{5,}\b", title or "", re.IGNORECASE))


def top_reason(reasons):
    return reasons[0] if reasons else "sin hallazgos obvios"


def finalize_verdict(verdict, reasons, warnings):
    if verdict in {"rechazar", "revisar"}:
        return verdict
    if warnings:
        return "aprobable con cautela"
    return "aprobable"


def fetch_changes(pr_id, token):
    iterations = api_json(f"/pullRequests/{pr_id}/iterations?api-version=7.1-preview.1", token)
    if not iterations.get("count"):
        return []
    last_iteration = iterations["value"][-1]["id"]
    changes = api_json(f"/pullRequests/{pr_id}/iterations/{last_iteration}/changes?api-version=7.1-preview.1", token)
    out = []
    for entry in changes.get("changeEntries", []):
        path = (entry.get("item") or {}).get("path") or entry.get("originalPath")
        out.append({"path": path, "changeType": entry.get("changeType")})
    return out


def summarize_scope(paths):
    if not paths:
        return "sin archivos detectados"
    known = [p for p in paths if (p or "").startswith("/dataPack/") or (p or "").startswith("/force-app/")]
    if not known:
        return "otros"
    if all((p or "").startswith("/dataPack/") for p in known):
        return "solo dataPack"
    if all((p or "").startswith("/force-app/") for p in known):
        return "solo force-app"
    return "mixto"


def release_key_for_target(target):
    target = target or ""
    if target == "develop":
        return "release-06.1"
    if target == "develop-pr":
        return "release-06"
    if "releaseproyecto/r6" in target:
        return "release-06"
    m = re.search(r"r(\d+(?:[.-]\d+)?)", target, re.IGNORECASE)
    if m:
        num = m.group(1).replace('-', '.')
        # zero-pad número principal (6 → 06)
        parts = num.split('.')
        parts[0] = parts[0].zfill(2)
        return f"release-{'.'.join(parts)}"
    return None


def datapack_manifest_candidates(release_key, datatype):
    if not release_key:
        return []
    return [
        f"manifest-pipeline/{release_key}/manifest-datapack/{datatype}.yaml",
        f"manifest-pipeline/{release_key}/manifest/manifest-datapack/{datatype}.yaml",
        f"manifest-pipeline/{release_key}/manifest-baseline/manifest-datapack/{datatype}.yaml",
    ]


def forceapp_manifest_candidates(release_key):
    if not release_key:
        return []
    return [
        f"manifest-pipeline/{release_key}/manifest-forceapp/package-metadata.xml",
        f"manifest-pipeline/{release_key}/manifest/manifest-forceapp/package-metadata.xml",
        f"manifest-pipeline/{release_key}/manifest-baseline/manifest-forceapp/devops-basePackage.xml",
        f"manifest-pipeline/{release_key}/manifest-baseline/manifest-forceapp/devops-posPackage.xml",
    ]


def path_exists_in_ref(ref, path, token=None):
    out = git_lines(["ls-tree", "-r", "--name-only", ref, "--", path])
    if any(line.strip() == path for line in out):
        return True
    # Fallback: verificar via API de Azure si el git local está desactualizado
    if token:
        branch = ref.replace("origin/", "")
        content = file_content_from_api(path if path.startswith("/") else f"/{path}", branch, token)
        return content is not None
    return False


def file_content(ref, path):
    try:
        return subprocess.check_output(
            ["git", "-C", LOCAL_REPO, "show", f"{ref}:{path}"],
            text=True, timeout=5, stderr=subprocess.DEVNULL
        )
    except Exception:
        return None


def file_content_from_api(path, ref, token):
    """Lee el contenido de un archivo desde Azure DevOps API usando un branch/ref."""
    try:
        branch = ref.replace("origin/", "")
        url = (f"{ORG_URL}/{PROJECT}/_apis/git/repositories/{REPO_ID}/items"
               f"?path={path}&versionDescriptor.version={branch}"
               f"&versionDescriptor.versionType=branch&api-version=7.1")
        req = Request(url, headers={"Authorization": f"Bearer {token}"})
        with urlopen(req, timeout=15) as r:
            return r.read().decode("utf-8", "replace")
    except Exception:
        return None


def datapack_component_from_path(path):
    parts = (path or "").strip("/").split("/")
    if len(parts) < 4 or parts[0] != "dataPack":
        return None, None
    datatype = parts[1]
    folder = parts[2]
    return datatype, folder


def forceapp_member_from_path(path):
    parts = (path or "").strip("/").split("/")
    if len(parts) < 5 or parts[0] != "force-app":
        return None
    filename = parts[-1]
    name = filename.split(".")[0]
    return name


def _load_deploy_sequence(target_ref):
    """Retorna el conjunto de manifestFiles normalizados de todos los deploy sequences."""
    manifests = set()
    for path in ("manifest/deploysequence.json",
                 "manifest-pipeline/release-06.1/deploy-secuence-r6.1.json",
                 "manifest-pipeline/deploysequence.json"):
        content = file_content(target_ref, path)
        if content:
            try:
                data = json.loads(content)
                for b in data.get("builds", []):
                    mf = b.get("manifestFile", "")
                    if mf:
                        manifests.add(mf.lstrip("./").lstrip(".").lstrip("/"))
            except Exception:
                pass
    return manifests


def yaml_in_deploy_sequence(target_ref, release_key, datatype):
    """Verifica que el YAML del datatype esté referenciado en el deploy sequence."""
    deploy_manifests = _load_deploy_sequence(target_ref)
    if not deploy_manifests:
        return True  # si no se puede leer, no bloquear
    for candidate in datapack_manifest_candidates(release_key, datatype):
        normalized = candidate.lstrip("./").lstrip(".").lstrip("/")
        if normalized in deploy_manifests:
            return True
    return False


def component_in_datapack_manifest(target_ref, release_key, datatype, folder):
    for candidate in datapack_manifest_candidates(release_key, datatype):
        content = file_content(target_ref, candidate)
        if content and folder in content:
            return True, candidate
    return False, None


def component_in_forceapp_manifest(target_ref, release_key, member_name):
    for candidate in forceapp_manifest_candidates(release_key):
        content = file_content(target_ref, candidate)
        if content and member_name in content:
            return True, candidate
    return False, None


def check_yaml_duplicates(source_ref, paths, token=None):
    """Detecta componentes duplicados en archivos YAML del PR."""
    duplicates = []
    yaml_files = [p for p in paths if p.endswith('.yaml') or p.endswith('.yml')]
    
    for yaml_path in yaml_files:
        content = None
        if token:
            content = file_content_from_api(yaml_path, source_ref, token)
        if not content:
            content = file_content(source_ref, yaml_path.lstrip('/'))
        if not content:
            continue
        
        lines = content.split('\n')
        seen = {}
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped and stripped.startswith('- ') and not stripped.startswith('# '):
                normalized = ' '.join(stripped.split())
                if normalized in seen:
                    component = normalized[2:].strip()
                    duplicates.append({
                        'file': yaml_path,
                        'component': component,
                        'lines': [seen[normalized], i]
                    })
                else:
                    seen[normalized] = i
    
    return duplicates


def classify(pr, changes, token=None):
    title = pr.get("title", "")
    source = normalize_ref(pr.get("sourceRefName", ""))
    target = normalize_ref(pr.get("targetRefName", ""))
    target_ref = f"origin/{target}" if target else None
    source_ref = f"origin/{source}" if source else None
    pr_id = pr.get("pullRequestId")
    paths = [c.get("path") for c in changes if c.get("path")]
    reasons = []
    warnings = []
    verdict = "aprobable"
    release_key = release_key_for_target(target)

    if not title_has_work_item(title):
        verdict = "rechazar"
        reasons.append("título sin work item claro")
    
    # Verificar duplicados en YAMLs
    if source_ref:
        duplicates = check_yaml_duplicates(source_ref, paths, token=token)
        if duplicates:
            verdict = "rechazar"
            for dup in duplicates:
                reasons.append(f"componente duplicado en {dup['file']}: {dup['component']} (líneas {dup['lines'][0]}, {dup['lines'][1]})")

    if target == "develop":
        if not re.search(r"r?6[.\-]1", source, re.IGNORECASE):
            verdict = "rechazar"
            reasons.append("PR hacia develop sin release r6.1 en rama fuente")
        if "sp69" not in source.lower():
            verdict = "rechazar"
            reasons.append("PR hacia develop sin sprint sp69 en rama fuente")
    elif target == "develop-pr":
        if verdict != "rechazar":
            warnings.append("target develop-pr, rama bugfix flexible")
    elif target == "releaseproyecto/r6":
        pass  # flujo válido, sin restricciones adicionales
    else:
        if verdict == "aprobable":
            verdict = "revisar"
        reasons.append(f"target {target} fuera del flujo principal")

    scope = summarize_scope(paths)
    datapack_paths = [p for p in paths if p.startswith("/dataPack/")]
    forceapp_paths = [p for p in paths if p.startswith("/force-app/")]

    if datapack_paths:
        data_pack_files = [p for p in datapack_paths if p.endswith("_DataPack.json")]
        parent_keys_deleted = [p for p in datapack_paths if p.endswith("_ParentKeys.json")]

        if target_ref and release_key:
            for p in data_pack_files:
                datatype, folder = datapack_component_from_path(p)
                if not datatype or not folder:
                    continue
                if not any(cp.endswith(f"/{datatype}.yaml") for cp in paths):
                    ok, manifest = component_in_datapack_manifest(target_ref, release_key, datatype, folder)
                    if not ok:
                        verdict = "rechazar"
                        reasons.append(f"dataPack {folder} no encontrado en manifest base {release_key}")
                    else:
                        if not yaml_in_deploy_sequence(target_ref, release_key, datatype):
                            verdict = "rechazar"
                            reasons.append(f"dataPack {datatype}.yaml no está en el deploy sequence")

    if forceapp_paths:
        package_in_pr = any(p.endswith("package-metadata.xml") for p in paths)
        source_ref = f"origin/{source}" if source else None
        for p in forceapp_paths:
            if p.endswith("package-metadata.xml"):
                continue
            member = forceapp_member_from_path(p)
            if not member or not target_ref or not release_key:
                continue
            exists_in_target = path_exists_in_ref(target_ref, p.lstrip("/"), token=token)
            if exists_in_target:
                continue
            # Buscar package-metadata.xml en rama origen
            if package_in_pr or (source_ref and component_in_forceapp_manifest(source_ref, release_key, member)[0]):
                continue
            # Si no está en origen, buscar en manifest del destino
            ok, manifest = component_in_forceapp_manifest(target_ref, release_key, member)
            if not ok:
                verdict = "rechazar"
                reasons.append(f"force-app nuevo sin package-metadata.xml en origen ni en manifest destino: {member}")



    if any((p or "").endswith(".md") for p in paths):
        warnings.append("contiene archivo .md — revisar si hay tarea manual pendiente")

    final_verdict = finalize_verdict(verdict, reasons, warnings)

    return {
        "id": pr_id,
        "title": title,
        "source": source,
        "target": target,
        "createdBy": (pr.get("createdBy") or {}).get("displayName"),
        "verdict": final_verdict,
        "reasons": reasons,
        "warnings": warnings,
        "scope": scope,
        "changedFiles": len(paths),
        "topFiles": paths[:8],
        "summary": top_reason(reasons if reasons else warnings),
    }


def main():
    token = get_token()
    prs = json.loads(run([
        "az", "repos", "pr", "list",
        "--status", "active",
        "--repository", REPOSITORY,
        "--org", ORG_URL,
        "--project", PROJECT,
        "-o", "json",
    ]))
    prs = [pr for pr in prs if normalize_ref(pr.get("targetRefName", "")) in {"develop", "develop-pr"}]

    state = load_state()
    seen = state.setdefault("seen", {})
    reports = []

    for pr in prs:
        pr_id = str(pr["pullRequestId"])
        fingerprint = f"{pr.get('lastMergeSourceCommit', {}).get('commitId', '')}:{pr.get('status', '')}"
        if seen.get(pr_id) == fingerprint:
            continue
        changes = fetch_changes(pr_id, token)
        report = classify(pr, changes)
        report["creationDate"] = pr.get("creationDate")
        reports.append(report)
        seen[pr_id] = fingerprint

    save_state(state)

    if not reports:
        print("NO_CHANGES")
        return

    priority = {"rechazar": 0, "revisar": 1, "aprobable con cautela": 2, "aprobable": 3}
    for rep in sorted(reports, key=lambda x: (priority.get(x['verdict'], 9), x['id'])):
        print(json.dumps(rep, ensure_ascii=False))


if __name__ == "__main__":
    main()
