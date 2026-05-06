#!/usr/bin/env python3
"""
Script de diagnóstico para ver los mensajes en el canal de Slack
y entender qué patrón buscar para encontrar los threads de PRs.
"""

import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv(Path(__file__).parent / ".env")

# Agregar path para imports
sys.path.insert(0, str(Path(__file__).parent))

from integrations.slack import slack_api, get_slack_channel

def debug_slack_messages(limit=20):
    """Muestra los últimos mensajes del canal de Slack para debugging."""
    
    channel = get_slack_channel()
    print(f"📢 Canal de Slack: {channel}")
    print(f"📊 Obteniendo últimos {limit} mensajes...\n")
    
    result = slack_api("conversations.history", {"channel": channel, "limit": limit})
    
    if not result.get("ok"):
        print(f"❌ Error: {result.get('error', 'unknown')}")
        return
    
    messages = result.get("messages", [])
    print(f"✅ Encontrados {len(messages)} mensajes\n")
    print("=" * 80)
    
    for i, msg in enumerate(messages, 1):
        print(f"\n📨 Mensaje #{i}")
        print(f"   Timestamp: {msg.get('ts')}")
        print(f"   Usuario: {msg.get('user', 'N/A')}")
        print(f"   Bot: {msg.get('bot_id', 'N/A')}")
        print(f"   Tipo: {msg.get('type', 'N/A')}")
        print(f"   Subtype: {msg.get('subtype', 'N/A')}")
        
        # Texto del mensaje
        text = msg.get('text', '')
        if text:
            print(f"   Texto: {text[:200]}")
        
        # Attachments
        attachments = msg.get('attachments', [])
        if attachments:
            print(f"   Attachments: {len(attachments)}")
            for j, att in enumerate(attachments, 1):
                print(f"      Attachment #{j}:")
                if 'title' in att:
                    print(f"         Título: {att['title']}")
                if 'title_link' in att:
                    print(f"         Link: {att['title_link']}")
                if 'text' in att:
                    print(f"         Texto: {att['text'][:100]}")
        
        # Buscar patrones de PR
        msg_json = json.dumps(msg)
        
        # Patrones comunes
        patterns = [
            "pullrequest/",
            "pull request",
            "PR #",
            "_git/",
            "/pullrequest/",
        ]
        
        found_patterns = []
        for pattern in patterns:
            if pattern.lower() in msg_json.lower():
                found_patterns.append(pattern)
        
        if found_patterns:
            print(f"   🔍 Patrones encontrados: {', '.join(found_patterns)}")
        
        # Si tiene thread
        if 'thread_ts' in msg:
            print(f"   💬 Thread: {msg['thread_ts']}")
        
        print("-" * 80)
    
    print("\n" + "=" * 80)
    print("\n💡 Busca mensajes que contengan información de PRs")
    print("   y anota el patrón que usan (ej: 'pullrequest/123', 'PR #123', etc.)")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Debug de mensajes de Slack")
    parser.add_argument("--limit", type=int, default=20, help="Número de mensajes a obtener (default: 20)")
    
    args = parser.parse_args()
    
    try:
        debug_slack_messages(args.limit)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
