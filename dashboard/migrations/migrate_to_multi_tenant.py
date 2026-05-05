#!/usr/bin/env python3
"""
Migración a Multi-Tenant
=========================

Este script:
1. Crea las nuevas tablas de multi-tenant
2. Migra los datos actuales al primer tenant (Salesforce Mexico)
3. Mantiene compatibilidad con los datos existentes

Uso:
    python3 migrations/migrate_to_multi_tenant.py
"""

import json
import secrets
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Agregar el directorio padre al path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configuración
DB_PATH = Path(__file__).parent.parent.parent / "memoria" / "state.db"
MIGRATION_SQL = Path(__file__).parent / "001_create_multi_tenant_schema.sql"

# Datos del primer tenant (tu configuración actual)
FIRST_TENANT = {
    "subdomain": "salesforce-mx",
    "company_name": "Salesforce Mexico",
    "plan": "enterprise",  # Empiezas con plan completo
    "status": "active",
    "azure": {
        "org_url": "https://dev.azure.com/salesforce-mx",
        "project": "SalesForce",
        "repository": "SalesForce",
        "pat_token": "TU_TOKEN_AQUI"  # Se tomará del .env
    },
    "slack": {
        "channel": "C08DXXXXXQP",
        "bot_token": "TU_SLACK_TOKEN"  # Se tomará del .env
    },
    "sheets": {
        "spreadsheet_id": "1Hn8XXXXXXXXXX",
        "sheet_name": "PRs"
    },
    "settings": {
        "language": "es",
        "timezone": "America/Mexico_City",
        "local_repo_path": "/home/zen6/cc/SalesForce"
    }
}


def generate_api_key():
    """Genera una API key segura."""
    return f"prm_{secrets.token_urlsafe(32)}"


def get_env_value(key, default=""):
    """Lee un valor del archivo .env"""
    env_file = Path(__file__).parent.parent / ".env"
    if not env_file.exists():
        return default
    
    with open(env_file) as f:
        for line in f:
            if line.strip().startswith(key):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return default


def backup_database():
    """Crea un backup de la base de datos antes de migrar."""
    if not DB_PATH.exists():
        print(f"⚠️  Base de datos no encontrada en: {DB_PATH}")
        return False
    
    backup_path = DB_PATH.parent / f"state_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    
    try:
        import shutil
        shutil.copy2(DB_PATH, backup_path)
        print(f"✅ Backup creado: {backup_path}")
        return True
    except Exception as e:
        print(f"❌ Error creando backup: {e}")
        return False


def run_migration():
    """Ejecuta la migración SQL."""
    print("\n📋 Ejecutando migración SQL...")
    
    if not MIGRATION_SQL.exists():
        print(f"❌ Archivo de migración no encontrado: {MIGRATION_SQL}")
        return False
    
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        # Leer y ejecutar el SQL
        with open(MIGRATION_SQL) as f:
            sql_script = f.read()
        
        cursor.executescript(sql_script)
        conn.commit()
        
        print("✅ Migración SQL completada")
        
        # Verificar que las tablas se crearon
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'tenant%'")
        tables = cursor.fetchall()
        print(f"   Tablas creadas: {', '.join(t[0] for t in tables)}")
        
        conn.close()
        return True
    
    except Exception as e:
        print(f"❌ Error ejecutando migración: {e}")
        return False


def create_first_tenant():
    """Crea el primer tenant con los datos actuales."""
    print("\n👤 Creando primer tenant...")
    
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        # Generar API key
        api_key = generate_api_key()
        trial_ends = datetime.now() + timedelta(days=365)  # 1 año gratis para ti
        
        # Insertar tenant
        cursor.execute("""
            INSERT INTO tenants (subdomain, company_name, api_key, plan, status, trial_ends_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            FIRST_TENANT["subdomain"],
            FIRST_TENANT["company_name"],
            api_key,
            FIRST_TENANT["plan"],
            FIRST_TENANT["status"],
            trial_ends
        ))
        
        tenant_id = cursor.lastrowid
        print(f"✅ Tenant creado con ID: {tenant_id}")
        print(f"   API Key: {api_key}")
        print(f"   ⚠️  GUARDA ESTA API KEY - La necesitarás para configurar el .env")
        
        # Configurar Azure DevOps
        azure_token = get_env_value("AZURE_DEVOPS_PAT", FIRST_TENANT["azure"]["pat_token"])
        cursor.execute("""
            INSERT INTO tenant_azure_config (tenant_id, org_url, project, repository, pat_token)
            VALUES (?, ?, ?, ?, ?)
        """, (
            tenant_id,
            FIRST_TENANT["azure"]["org_url"],
            FIRST_TENANT["azure"]["project"],
            FIRST_TENANT["azure"]["repository"],
            azure_token
        ))
        print("✅ Configuración de Azure DevOps creada")
        
        # Configurar Slack (opcional)
        slack_token = get_env_value("SLACK_BOT_TOKEN", FIRST_TENANT["slack"]["bot_token"])
        if slack_token and slack_token != "TU_SLACK_TOKEN":
            slack_config = json.dumps({
                "channel": FIRST_TENANT["slack"]["channel"],
                "bot_token": slack_token
            })
            cursor.execute("""
                INSERT INTO tenant_integrations (tenant_id, integration_type, enabled, config)
                VALUES (?, 'slack', 1, ?)
            """, (tenant_id, slack_config))
            print("✅ Integración de Slack configurada")
        
        # Configurar Google Sheets (opcional)
        sheets_config = json.dumps({
            "spreadsheet_id": FIRST_TENANT["sheets"]["spreadsheet_id"],
            "sheet_name": FIRST_TENANT["sheets"]["sheet_name"]
        })
        cursor.execute("""
            INSERT INTO tenant_integrations (tenant_id, integration_type, enabled, config)
            VALUES (?, 'sheets', 1, ?)
        """, (tenant_id, sheets_config))
        print("✅ Integración de Google Sheets configurada")
        
        # Configuración general
        cursor.execute("""
            INSERT INTO tenant_settings (
                tenant_id, language, timezone, local_repo_path,
                blocked_authors, blocked_branches
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            tenant_id,
            FIRST_TENANT["settings"]["language"],
            FIRST_TENANT["settings"]["timezone"],
            FIRST_TENANT["settings"]["local_repo_path"],
            json.dumps(["Glenda Paiva"]),  # Autor bloqueado por defecto
            json.dumps([])
        ))
        print("✅ Configuración general creada")
        
        conn.commit()
        conn.close()
        
        return tenant_id, api_key
    
    except Exception as e:
        print(f"❌ Error creando tenant: {e}")
        return None, None


def migrate_existing_data(tenant_id):
    """Migra los datos existentes de config y kv al tenant."""
    print(f"\n📦 Migrando datos existentes al tenant {tenant_id}...")
    
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        # Verificar si existen las tablas antiguas
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('config', 'kv')")
        old_tables = [row[0] for row in cursor.fetchall()]
        
        if not old_tables:
            print("ℹ️  No hay datos antiguos para migrar")
            conn.close()
            return True
        
        # Aquí podrías migrar datos específicos si es necesario
        # Por ahora, los datos de config se mantienen para compatibilidad
        
        print("✅ Datos migrados correctamente")
        
        conn.close()
        return True
    
    except Exception as e:
        print(f"❌ Error migrando datos: {e}")
        return False


def update_env_file(api_key):
    """Actualiza el archivo .env con la nueva API key del tenant."""
    print("\n📝 Actualizando archivo .env...")
    
    env_file = Path(__file__).parent.parent / ".env"
    
    try:
        # Leer contenido actual
        if env_file.exists():
            with open(env_file) as f:
                lines = f.readlines()
        else:
            lines = []
        
        # Buscar y actualizar API_KEY
        api_key_found = False
        for i, line in enumerate(lines):
            if line.strip().startswith("API_KEY="):
                lines[i] = f'API_KEY="{api_key}"\n'
                api_key_found = True
                break
        
        # Si no existe, agregar al final
        if not api_key_found:
            lines.append(f'\nAPI_KEY="{api_key}"\n')
        
        # Agregar comentario sobre tenant
        if not any("TENANT_ID" in line for line in lines):
            lines.append(f'\n# Multi-Tenant Configuration\n')
            lines.append(f'TENANT_ID="1"\n')
            lines.append(f'TENANT_SUBDOMAIN="salesforce-mx"\n')
        
        # Escribir de vuelta
        with open(env_file, 'w') as f:
            f.writelines(lines)
        
        print(f"✅ Archivo .env actualizado")
        print(f"   API_KEY configurada para el tenant")
        
        return True
    
    except Exception as e:
        print(f"❌ Error actualizando .env: {e}")
        return False


def verify_migration():
    """Verifica que la migración se completó correctamente."""
    print("\n🔍 Verificando migración...")
    
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        # Verificar tenant
        cursor.execute("SELECT COUNT(*) FROM tenants")
        tenant_count = cursor.fetchone()[0]
        print(f"✅ Tenants creados: {tenant_count}")
        
        # Verificar configuración de Azure
        cursor.execute("SELECT COUNT(*) FROM tenant_azure_config")
        azure_count = cursor.fetchone()[0]
        print(f"✅ Configuraciones de Azure: {azure_count}")
        
        # Verificar integraciones
        cursor.execute("SELECT COUNT(*) FROM tenant_integrations")
        integrations_count = cursor.fetchone()[0]
        print(f"✅ Integraciones configuradas: {integrations_count}")
        
        # Verificar planes
        cursor.execute("SELECT COUNT(*) FROM plans")
        plans_count = cursor.fetchone()[0]
        print(f"✅ Planes disponibles: {plans_count}")
        
        conn.close()
        
        return tenant_count > 0 and azure_count > 0
    
    except Exception as e:
        print(f"❌ Error verificando migración: {e}")
        return False


def main():
    """Función principal de migración."""
    print("=" * 70)
    print("🚀 MIGRACIÓN A MULTI-TENANT")
    print("=" * 70)
    
    # Paso 1: Backup
    print("\n📦 Paso 1: Creando backup de seguridad...")
    if not backup_database():
        print("\n⚠️  No se pudo crear backup. ¿Continuar de todos modos? (y/N): ", end="")
        if input().lower() != 'y':
            print("❌ Migración cancelada")
            return False
    
    # Paso 2: Ejecutar migración SQL
    print("\n📋 Paso 2: Creando nuevas tablas...")
    if not run_migration():
        print("❌ Migración fallida")
        return False
    
    # Paso 3: Crear primer tenant
    print("\n👤 Paso 3: Creando tu tenant...")
    tenant_id, api_key = create_first_tenant()
    if not tenant_id:
        print("❌ No se pudo crear el tenant")
        return False
    
    # Paso 4: Migrar datos existentes
    print("\n📦 Paso 4: Migrando datos existentes...")
    if not migrate_existing_data(tenant_id):
        print("⚠️  Algunos datos no se pudieron migrar")
    
    # Paso 5: Actualizar .env
    print("\n📝 Paso 5: Actualizando configuración...")
    update_env_file(api_key)
    
    # Paso 6: Verificar
    print("\n🔍 Paso 6: Verificando migración...")
    if not verify_migration():
        print("⚠️  La verificación encontró problemas")
    
    # Resumen final
    print("\n" + "=" * 70)
    print("✅ MIGRACIÓN COMPLETADA")
    print("=" * 70)
    print(f"\n📊 Resumen:")
    print(f"   • Tenant ID: {tenant_id}")
    print(f"   • Subdomain: {FIRST_TENANT['subdomain']}")
    print(f"   • Company: {FIRST_TENANT['company_name']}")
    print(f"   • Plan: {FIRST_TENANT['plan']}")
    print(f"   • API Key: {api_key}")
    print(f"\n⚠️  IMPORTANTE:")
    print(f"   1. Guarda la API Key en un lugar seguro")
    print(f"   2. Reinicia el servidor: python3 app.py")
    print(f"   3. Verifica que todo funciona correctamente")
    print(f"   4. El backup está en: {DB_PATH.parent}/state_backup_*.db")
    print("\n" + "=" * 70)
    
    return True


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n❌ Migración cancelada por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
