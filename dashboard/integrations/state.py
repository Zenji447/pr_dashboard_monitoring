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
