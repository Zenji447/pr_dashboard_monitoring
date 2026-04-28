#!/usr/bin/env python3
"""Migra datos de JSON files a SQLite (ejecutar una sola vez)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from integrations.state import (
    save_auto_approve_config, save_blocked_authors, save_blocked_branches, save_state
)

BASE = Path(__file__).parent.parent / "memoria"

def migrate(path, save_fn, label):
    if path.exists():
        data = json.loads(path.read_text())
        save_fn(data)
        print(f"✅ {label} migrado")
    else:
        print(f"⚠️  {label}: archivo no encontrado, omitiendo")

migrate(BASE / "auto_approve_config.json", save_auto_approve_config, "auto_approve_config")
migrate(BASE / "blocked_authors.json", save_blocked_authors, "blocked_authors")
migrate(BASE / "blocked_branches.json", save_blocked_branches, "blocked_branches")

# Migrar state.json desde la ruta del script original
STATE_PATH = Path("/home/zen6/.openclaw/workspace/state/salesforce-pr-watch.json")
if STATE_PATH.exists():
    state = json.loads(STATE_PATH.read_text())
    save_state(state)
    print("✅ state migrado")
else:
    print("⚠️  state: archivo no encontrado, omitiendo")

print("\nMigración completada. La DB está en memoria/state.db")
