import logging
import os
import threading
from pathlib import Path

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from utils import minutes_between, retry

logger = logging.getLogger("pr_dashboard")

# ── Configuración dinámica por tenant ─────────────────────────────────────────

def _get_sheets_config():
    """Obtiene la configuración de Google Sheets del tenant actual."""
    from integrations.tenant_context import get_current_tenant
    
    tenant = get_current_tenant()
    if tenant:
        try:
            integration = tenant.get_integration('sheets')
            if integration and integration['enabled']:
                return integration['config']
        except Exception as e:
            logger.warning(f"Error obteniendo config de Sheets del tenant: {e}")
    
    # Fallback a variables de entorno (para compatibilidad)
    return {
        'spreadsheet_id': os.getenv("GOOGLE_SHEET_ID", "1jsYHmGm-2eN5986bgN5jlPO86guNfWmnf980H4TsdO0"),
        'sheet_name': 'Hoja 1'
    }


def get_sheet_id():
    """Obtiene el ID de la hoja de cálculo del tenant actual."""
    config = _get_sheets_config()
    return config.get('spreadsheet_id') if config else None


def get_sheet_name():
    """Obtiene el nombre de la hoja del tenant actual."""
    config = _get_sheets_config()
    return config.get('sheet_name', 'Hoja 1') if config else 'Hoja 1'


def is_sheets_enabled():
    """Verifica si Google Sheets está habilitado para el tenant actual."""
    from integrations.tenant_context import get_current_tenant
    
    tenant = get_current_tenant()
    if tenant:
        return tenant.has_integration('sheets')
    
    # Fallback: si hay sheet_id, está habilitado
    return get_sheet_id() is not None


# Para compatibilidad con código existente
SHEET_ID = get_sheet_id()
CREDS_PATH = Path(os.getenv("GOOGLE_CREDS_PATH", "../memoria/service-account-key.json"))
if not CREDS_PATH.is_absolute():
    CREDS_PATH = Path(__file__).parent.parent.parent / CREDS_PATH

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


def pr_to_row(pr, deploy_status="", deploy_date="", approval_date="", auto_approved=False):
    created   = pr.get("creationDate", "") or pr.get("closedDate", "")
    completed = pr.get("closedDate", "")
    t_review  = minutes_between(created, approval_date)
    t_merge   = minutes_between(approval_date, completed)
    t_deploy  = minutes_between(completed, deploy_date)
    t_total   = minutes_between(created, deploy_date) if deploy_date else minutes_between(created, completed)
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


def _find_row(sheet, pr_id):
    result = sheet.values().get(spreadsheetId=SHEET_ID, range="Hoja 1!A:A").execute()
    for i, row in enumerate(result.get("values", []), start=1):
        if row and str(row[0]) == str(pr_id):
            return i
    return None


def _ensure_headers(sheet):
    result = sheet.values().get(spreadsheetId=SHEET_ID, range="Hoja 1!A1:A1").execute()
    if not result.get("values"):
        sheet.values().update(
            spreadsheetId=SHEET_ID, range="Hoja 1!A1",
            valueInputOption="RAW", body={"values": [SHEET_HEADERS]},
        ).execute()


def append_pr(pr_data, auto_approved=False, approval_date=""):
    def _run():
        try:
            def _do():
                svc = _sheets_service()
                sheet = svc.spreadsheets()
                _ensure_headers(sheet)
                pr_id = pr_data.get("pullRequestId") or pr_data.get("id")
                if _find_row(sheet, pr_id):
                    return
                row = pr_to_row(pr_data, auto_approved=auto_approved, approval_date=approval_date)
                sheet.values().append(
                    spreadsheetId=SHEET_ID, range="Hoja 1!A1",
                    valueInputOption="RAW", insertDataOption="INSERT_ROWS",
                    body={"values": [row]},
                ).execute()
                logger.info("[sheets] PR %s registrado", pr_id)
            retry(_do, retries=2, label="sheets.append")
        except Exception as e:
            logger.error("[sheets] append error PR %s: %s",
                         pr_data.get("pullRequestId") or pr_data.get("id"), e)
    threading.Thread(target=_run, daemon=True).start()


def update_deploy(pr_id, deploy_status, deploy_date=""):
    def _run():
        try:
            def _do():
                svc = _sheets_service()
                sheet = svc.spreadsheets()
                row_num = _find_row(sheet, pr_id)
                if not row_num:
                    return
                row_data = sheet.values().get(
                    spreadsheetId=SHEET_ID, range=f"Hoja 1!A{row_num}:R{row_num}"
                ).execute().get("values", [[]])[0]
                created   = row_data[4] if len(row_data) > 4 else ""
                approval  = row_data[5] if len(row_data) > 5 else ""
                completed = row_data[6] if len(row_data) > 6 else ""
                deploy_str = deploy_date[:16].replace("T", " ") if deploy_date else ""
                updates = [
                    (f"Hoja 1!H{row_num}", [[deploy_str]]),
                    (f"Hoja 1!I{row_num}", [[minutes_between(created, approval)]]),
                    (f"Hoja 1!J{row_num}", [[minutes_between(approval, completed)]]),
                    (f"Hoja 1!K{row_num}", [[minutes_between(completed, deploy_str)]]),
                    (f"Hoja 1!L{row_num}", [[minutes_between(created, deploy_str) if deploy_str else minutes_between(created, completed)]]),
                    (f"Hoja 1!O{row_num}", [[deploy_status]]),
                ]
                for rng, vals in updates:
                    sheet.values().update(
                        spreadsheetId=SHEET_ID, range=rng,
                        valueInputOption="RAW", body={"values": vals},
                    ).execute()
                logger.info("[sheets] Deploy PR %s actualizado: %s", pr_id, deploy_status)
            retry(_do, retries=2, label="sheets.update_deploy")
        except Exception as e:
            logger.error("[sheets] update deploy error PR %s: %s", pr_id, e)
    threading.Thread(target=_run, daemon=True).start()


def export_range(prs, auto_approved_ids, blocked_authors, token, get_policy_fn, get_approval_fn, get_deploy_fn):
    """Exporta una lista de PRs al Sheet, omitiendo duplicados."""
    rows = []
    for pr in prs:
        pr_id = pr["id"]
        pr["blocked"] = (pr.get("createdBy") or "").lower().strip() in blocked_authors
        try:
            pr["policyStatus"] = get_policy_fn(pr_id, token)
        except Exception:
            pr["policyStatus"] = ""
        approval_date = get_approval_fn(pr_id, token) or pr.get("closedDate", "")
        deploy_st, deploy_date = get_deploy_fn(pr_id, pr.get("mergeCommit"), pr.get("closedDate"), pr.get("target"))
        rows.append(pr_to_row(pr, deploy_status=deploy_st, deploy_date=deploy_date,
                               approval_date=approval_date, auto_approved=pr_id in auto_approved_ids))

    def _do():
        svc = _sheets_service()
        sheet = svc.spreadsheets()
        existing = sheet.values().get(spreadsheetId=SHEET_ID, range="Hoja 1").execute().get("values", [])
        existing_ids = {r[0] for r in existing[1:] if r} if len(existing) > 1 else set()
        new_rows = [r for r in rows if str(r[0]) not in existing_ids]
        if not new_rows:
            return 0
        sheet.values().append(
            spreadsheetId=SHEET_ID, range="Hoja 1",
            valueInputOption="RAW", insertDataOption="INSERT_ROWS",
            body={"values": new_rows},
        ).execute()
        return len(new_rows)
    return retry(_do, retries=3, label="sheets.export")
