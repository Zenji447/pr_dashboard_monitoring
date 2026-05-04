import json
import sqlite3
import threading
from pathlib import Path

_DB_PATH = Path(__file__).parent.parent.parent / "memoria" / "state.db"
_lock = threading.Lock()


def _conn():
    con = sqlite3.connect(str(_DB_PATH))
    con.execute("""
        CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL)
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT NOT NULL)
    """)
    # Tabla para historial de cambios en reglas
    con.execute("""
        CREATE TABLE IF NOT EXISTS rule_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_id TEXT NOT NULL,
            rule_type TEXT NOT NULL,
            action TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            changed_by TEXT,
            changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ip_address TEXT
        )
    """)
    con.commit()
    return con


def _get(key, default=None):
    with _lock:
        con = _conn()
        row = con.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        con.close()
    return json.loads(row[0]) if row else default


def _set(key, value):
    with _lock:
        con = _conn()
        con.execute("INSERT OR REPLACE INTO kv(key,value) VALUES(?,?)", (key, json.dumps(value)))
        con.commit()
        con.close()


# ── State (reemplaza state.json) ─────────────────────────────────────────────

def load_state():
    return _get("state", {"seen": {}})


def save_state(state):
    _set("state", state)


# ── Config files (reemplaza JSON files en memoria/) ──────────────────────────

def get_config(key, default=None):
    with _lock:
        con = _conn()
        row = con.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
        con.close()
    return json.loads(row[0]) if row else default


def set_config(key, value):
    with _lock:
        con = _conn()
        con.execute("INSERT OR REPLACE INTO config(key,value) VALUES(?,?)", (key, json.dumps(value)))
        con.commit()
        con.close()


def load_auto_approve_config():
    return get_config("auto_approve", {"enabled": False, "branches": []})


def save_auto_approve_config(cfg):
    set_config("auto_approve", cfg)


def load_blocked_authors():
    return get_config("blocked_authors", ["Glenda Paiva"])


def save_blocked_authors(authors):
    set_config("blocked_authors", authors)


def load_blocked_branches():
    return get_config("blocked_branches", [])


def save_blocked_branches(branches):
    set_config("blocked_branches", branches)


# ── PR Validation Rules ──────────────────────────────────────────────────────

def load_pr_validation_rules():
    """Carga las reglas de validación de PR configurables."""
    default_rules = {
        "develop": {
            "release_pattern": r"r?6[.\-]1",
            "release_message": "PR hacia develop sin release r6.1 en rama fuente",
            "sprints": ["sp69", "sp70"],  # Lista de sprints activos (soporta múltiples)
            "sprint_message": "PR hacia develop sin sprint sp69 o sp70 en rama fuente",
            "enabled": True
        },
        "develop-pr": {
            "warning_message": "target develop-pr, rama bugfix flexible",
            "enabled": True
        },
        "releaseproyecto/r6": {
            "enabled": True
        }
    }
    rules = get_config("pr_validation_rules", default_rules)
    
    # Migración automática: convertir "sprint" (string) a "sprints" (lista)
    if "develop" in rules and "sprint" in rules["develop"] and "sprints" not in rules["develop"]:
        old_sprint = rules["develop"].pop("sprint")
        rules["develop"]["sprints"] = [old_sprint] if old_sprint else []
        save_pr_validation_rules(rules)
    
    return rules


def save_pr_validation_rules(rules):
    """Guarda las reglas de validación de PR."""
    set_config("pr_validation_rules", rules)


# ── Custom Validation Rules ──────────────────────────────────────────────────

def load_custom_rules():
    """Carga reglas de validación personalizadas."""
    default_custom_rules = {
        "manifest_validation": {
            "name": "Validación de Manifest",
            "description": "Valida que los archivos manifest cumplan con el formato requerido",
            "enabled": True,
            "type": "file_pattern",
            "pattern": r".*manifest.*\.xml",
            "validation_type": "content",
            "validation_pattern": r"<version>[\d\.]+</version>",
            "error_message": "Manifest sin versión válida",
            "severity": "error"  # error, warning, info
        },
        "metadata_validation": {
            "name": "Validación de Metadata",
            "description": "Valida archivos de metadata de Salesforce",
            "enabled": True,
            "type": "file_pattern",
            "pattern": r".*-meta\.xml$",
            "validation_type": "exists",
            "error_message": "Archivo metadata requerido",
            "severity": "warning"
        },
        "test_coverage": {
            "name": "Cobertura de Tests",
            "description": "Valida que existan tests para clases nuevas",
            "enabled": False,
            "type": "file_pattern",
            "pattern": r".*\.cls$",
            "validation_type": "requires_test",
            "error_message": "Clase sin test asociado",
            "severity": "warning"
        }
    }
    return get_config("custom_validation_rules", default_custom_rules)


def save_custom_rules(rules):
    """Guarda reglas de validación personalizadas."""
    set_config("custom_validation_rules", rules)


def get_all_validation_rules():
    """Obtiene todas las reglas de validación (branch + custom)."""
    return {
        "branch_rules": load_pr_validation_rules(),
        "custom_rules": load_custom_rules()
    }


def save_all_validation_rules(branch_rules=None, custom_rules=None):
    """Guarda todas las reglas de validación."""
    if branch_rules is not None:
        save_pr_validation_rules(branch_rules)
    if custom_rules is not None:
        save_custom_rules(custom_rules)


# ── Rule History (Auditoría de cambios) ──────────────────────────────────────

def log_rule_change(rule_id, rule_type, action, old_value=None, new_value=None, changed_by=None, ip_address=None):
    """
    Registra un cambio en una regla para auditoría.
    
    Args:
        rule_id: ID de la regla
        rule_type: 'branch' o 'custom'
        action: 'create', 'update', 'delete', 'toggle'
        old_value: Valor anterior (JSON string)
        new_value: Valor nuevo (JSON string)
        changed_by: Usuario que hizo el cambio
        ip_address: IP del usuario
    """
    with _lock:
        con = _conn()
        con.execute("""
            INSERT INTO rule_history (rule_id, rule_type, action, old_value, new_value, changed_by, ip_address)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (rule_id, rule_type, action, old_value, new_value, changed_by, ip_address))
        con.commit()
        con.close()


def get_rule_history(rule_id=None, rule_type=None, limit=100):
    """
    Obtiene el historial de cambios en reglas.
    
    Args:
        rule_id: Filtrar por ID de regla (opcional)
        rule_type: Filtrar por tipo de regla (opcional)
        limit: Número máximo de registros
    
    Returns:
        Lista de cambios ordenados por fecha (más reciente primero)
    """
    with _lock:
        con = _conn()
        query = "SELECT * FROM rule_history WHERE 1=1"
        params = []
        
        if rule_id:
            query += " AND rule_id = ?"
            params.append(rule_id)
        
        if rule_type:
            query += " AND rule_type = ?"
            params.append(rule_type)
        
        query += " ORDER BY changed_at DESC LIMIT ?"
        params.append(limit)
        
        cursor = con.execute(query, params)
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        con.close()
        
        return [dict(zip(columns, row)) for row in rows]


def get_rule_history_stats():
    """
    Obtiene estadísticas del historial de cambios.
    
    Returns:
        Dict con estadísticas
    """
    with _lock:
        con = _conn()
        
        # Total de cambios
        total = con.execute("SELECT COUNT(*) FROM rule_history").fetchone()[0]
        
        # Cambios por tipo de acción
        by_action = {}
        for row in con.execute("SELECT action, COUNT(*) as count FROM rule_history GROUP BY action"):
            by_action[row[0]] = row[1]
        
        # Cambios por tipo de regla
        by_type = {}
        for row in con.execute("SELECT rule_type, COUNT(*) as count FROM rule_history GROUP BY rule_type"):
            by_type[row[0]] = row[1]
        
        # Cambios recientes (últimas 24 horas)
        recent = con.execute("""
            SELECT COUNT(*) FROM rule_history 
            WHERE changed_at >= datetime('now', '-1 day')
        """).fetchone()[0]
        
        con.close()
        
        return {
            "total": total,
            "by_action": by_action,
            "by_type": by_type,
            "recent_24h": recent
        }


def rollback_rule_change(history_id):
    """
    Revierte un cambio en una regla usando el historial.
    
    Args:
        history_id: ID del registro en rule_history
    
    Returns:
        Dict con resultado de la operación
    """
    with _lock:
        con = _conn()
        
        # Obtener el cambio del historial
        row = con.execute("SELECT * FROM rule_history WHERE id = ?", (history_id,)).fetchone()
        if not row:
            con.close()
            return {"ok": False, "error": "Cambio no encontrado"}
        
        columns = ["id", "rule_id", "rule_type", "action", "old_value", "new_value", "changed_by", "changed_at", "ip_address"]
        change = dict(zip(columns, row))
        
        con.close()
        
        # Aplicar el rollback según el tipo de acción
        try:
            if change["action"] == "create":
                # Si fue creación, eliminar la regla
                if change["rule_type"] == "custom":
                    rules = load_custom_rules()
                    if change["rule_id"] in rules:
                        del rules[change["rule_id"]]
                        save_custom_rules(rules)
                        log_rule_change(change["rule_id"], "custom", "delete", 
                                      old_value=change["new_value"], 
                                      changed_by="system_rollback")
            
            elif change["action"] == "delete":
                # Si fue eliminación, recrear la regla
                if change["rule_type"] == "custom" and change["old_value"]:
                    rules = load_custom_rules()
                    rules[change["rule_id"]] = json.loads(change["old_value"])
                    save_custom_rules(rules)
                    log_rule_change(change["rule_id"], "custom", "create", 
                                  new_value=change["old_value"], 
                                  changed_by="system_rollback")
            
            elif change["action"] in ["update", "toggle"]:
                # Si fue actualización, restaurar valor anterior
                if change["old_value"]:
                    if change["rule_type"] == "branch":
                        rules = load_pr_validation_rules()
                        rules[change["rule_id"]] = json.loads(change["old_value"])
                        save_pr_validation_rules(rules)
                    elif change["rule_type"] == "custom":
                        rules = load_custom_rules()
                        rules[change["rule_id"]] = json.loads(change["old_value"])
                        save_custom_rules(rules)
                    
                    log_rule_change(change["rule_id"], change["rule_type"], "update", 
                                  old_value=change["new_value"], 
                                  new_value=change["old_value"], 
                                  changed_by="system_rollback")
            
            return {"ok": True, "change": change}
        
        except Exception as e:
            return {"ok": False, "error": str(e)}
