#!/usr/bin/env python3
"""
Script para verificar y limpiar el guard de notificaciones de Slack
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from integrations.state import load_state, save_state

def check_guard():
    """Verifica el estado del guard de notificaciones."""
    state = load_state()
    slack_notifications = state.get("slack_notifications", {})
    approved_notified = state.get("approved_notified", [])
    
    print("=" * 80)
    print("🔍 ESTADO DEL GUARD DE NOTIFICACIONES")
    print("=" * 80)
    
    print(f"\n📊 Notificaciones en slack_notifications: {len(slack_notifications)}")
    if slack_notifications:
        print("\nÚltimas 10 notificaciones:")
        for i, (key, value) in enumerate(list(slack_notifications.items())[-10:]):
            print(f"   {i+1}. {key} → {value.get('timestamp', 'N/A')}")
    
    print(f"\n📊 PRs en approved_notified: {len(approved_notified)}")
    if approved_notified:
        print(f"   Últimos 10: {approved_notified[-10:]}")
    
    # Buscar PR 88357 específicamente
    pr_id = 88357
    print(f"\n🔎 Buscando PR {pr_id}:")
    
    approve_key = f"{pr_id}:approve"
    if approve_key in slack_notifications:
        print(f"   ✅ Encontrado en slack_notifications:")
        print(f"      {slack_notifications[approve_key]}")
    else:
        print(f"   ❌ NO encontrado en slack_notifications")
    
    if pr_id in approved_notified:
        print(f"   ✅ Encontrado en approved_notified")
    else:
        print(f"   ❌ NO encontrado en approved_notified")
    
    print("\n" + "=" * 80)


def clean_pr_guard(pr_id):
    """Limpia el guard para un PR específico."""
    state = load_state()
    
    # Limpiar de slack_notifications
    slack_notifications = state.get("slack_notifications", {})
    approve_key = f"{pr_id}:approve"
    
    if approve_key in slack_notifications:
        del slack_notifications[approve_key]
        print(f"✅ Eliminado {approve_key} de slack_notifications")
    
    # Limpiar de approved_notified
    approved_notified = state.get("approved_notified", [])
    if pr_id in approved_notified:
        approved_notified.remove(pr_id)
        print(f"✅ Eliminado {pr_id} de approved_notified")
    
    save_state(state)
    print(f"\n✅ Guard limpiado para PR {pr_id}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Verificar y limpiar guard de Slack")
    parser.add_argument("--clean", type=int, metavar="PR_ID", help="Limpiar guard para un PR específico")
    
    args = parser.parse_args()
    
    if args.clean:
        clean_pr_guard(args.clean)
    else:
        check_guard()
