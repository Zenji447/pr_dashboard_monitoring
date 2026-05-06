"""
Minimal implementation of check_salesforce_prs functions for multi-tenant system.
This replaces the original script that was in a different location.
"""

import json
import logging
import subprocess
from integrations.azure import get_org_url, get_project, get_repository

logger = logging.getLogger("pr_dashboard")


def normalize_ref(ref):
    """Normaliza una referencia de branch eliminando el prefijo refs/heads/."""
    return ref.replace("refs/heads/", "") if ref else ref


def fetch_changes(pr_id, token):
    """Obtiene los cambios de un PR."""
    try:
        result = subprocess.run([
            "az", "repos", "pr", "show", "--id", str(pr_id),
            "--org", get_org_url(), "--project", get_project(),
            "--output", "json"
        ], capture_output=True, text=True, check=True)
        
        pr_data = json.loads(result.stdout)
        
        # Obtener archivos modificados
        files_result = subprocess.run([
            "az", "repos", "pr", "list-files", "--id", str(pr_id),
            "--org", get_org_url(), "--project", get_project(),
            "--output", "json"
        ], capture_output=True, text=True, check=True)
        
        files_data = json.loads(files_result.stdout)
        
        return {
            "files": [f.get("path", "") for f in files_data],
            "additions": sum(f.get("linesAdded", 0) for f in files_data),
            "deletions": sum(f.get("linesDeleted", 0) for f in files_data),
        }
    except Exception as e:
        logger.warning(f"Error fetching changes for PR {pr_id}: {e}")
        return {"files": [], "additions": 0, "deletions": 0}


def get_my_vote(pr):
    """Obtiene mi voto en el PR."""
    try:
        # Obtener el usuario actual de Azure
        result = subprocess.run([
            "az", "account", "show", "--query", "user.name", "-o", "tsv"
        ], capture_output=True, text=True, check=False)
        
        if result.returncode != 0:
            logger.warning("No se pudo obtener el usuario actual de Azure")
            return "no_vote"
        
        current_user_email = result.stdout.strip().lower()
        
        reviewers = pr.get("reviewers", [])
        
        # Buscar específicamente MI voto
        for reviewer in reviewers:
            reviewer_email = reviewer.get("uniqueName", "").lower()
            reviewer_display = reviewer.get("displayName", "").lower()
            
            # Comparar por email o display name
            if current_user_email in reviewer_email or current_user_email in reviewer_display:
                vote = reviewer.get("vote", 0)
                if vote == 10:
                    return "approved"
                elif vote == -10:
                    return "rejected"
                elif vote == -5:
                    return "waiting"
                else:
                    return "no_vote"
        
        return "no_vote"
    except Exception as e:
        logger.warning(f"Error getting vote for PR: {e}")
        return "no_vote"


def classify(pr, changes, token=None):
    """Clasifica un PR basado en sus cambios y características."""
    try:
        pr_id = pr.get("pullRequestId", pr.get("id", ""))
        title = pr.get("title", "")
        description = pr.get("description", "")
        created_by = pr.get("createdBy", {}).get("displayName", "")
        
        # Análisis básico
        files = changes.get("files", [])
        additions = changes.get("additions", 0)
        deletions = changes.get("deletions", 0)
        
        # Clasificación simple
        reasons = []
        warnings = []
        
        # Verificar archivos críticos
        critical_files = [".config", ".json", ".xml", ".yml", ".yaml"]
        if any(any(ext in f for ext in critical_files) for f in files):
            reasons.append("Modifica archivos de configuración")
        
        # Verificar tamaño del cambio
        total_changes = additions + deletions
        if total_changes > 500:
            reasons.append("Cambio muy grande (>500 líneas)")
        elif total_changes > 200:
            warnings.append("Cambio mediano (>200 líneas)")
        
        # Verificar archivos de documentación
        doc_files = [".md", ".txt", ".doc"]
        if any(any(ext in f for ext in doc_files) for f in files):
            warnings.append("Incluye cambios en documentación")
        
        # Determinar veredicto
        if reasons:
            verdict = "revisar"
        elif warnings:
            verdict = "aprobable con cautela"
        else:
            verdict = "aprobable"
        
        return {
            "id": pr_id,
            "title": title,
            "createdBy": created_by,
            "verdict": verdict,
            "reasons": reasons,
            "warnings": warnings,
            "files": files,
            "additions": additions,
            "deletions": deletions,
        }
        
    except Exception as e:
        logger.error(f"Error classifying PR: {e}")
        return {
            "id": pr.get("pullRequestId", pr.get("id", "")),
            "title": pr.get("title", ""),
            "createdBy": pr.get("createdBy", {}).get("displayName", ""),
            "verdict": "revisar",
            "reasons": ["Error en clasificación"],
            "warnings": [],
            "files": [],
            "additions": 0,
            "deletions": 0,
        }