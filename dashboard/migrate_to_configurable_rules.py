#!/usr/bin/env python3
"""
Script de migración para integrar reglas configurables en check_salesforce_prs.py

Este script modifica automáticamente el script de validación para que use
las reglas configurables desde la base de datos en lugar de validaciones hardcoded.
"""

import re
import sys
from pathlib import Path
from datetime import datetime

SCRIPT_PATH = Path("../scripts/check_salesforce_prs.py")
BACKUP_SUFFIX = f".backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"

# Código de la nueva función a insertar
LOAD_CUSTOM_RULES_FUNCTION = '''
def load_custom_validation_rules():
    """Carga las reglas de validación personalizadas desde la base de datos."""
    try:
        import sys
        from pathlib import Path
        # Agregar el directorio del dashboard al path
        dashboard_path = Path(__file__).parent.parent / "dashboard"
        if str(dashboard_path) not in sys.path:
            sys.path.insert(0, str(dashboard_path))
        
        from integrations.state import load_custom_rules
        rules = load_custom_rules()
        # Filtrar solo reglas habilitadas
        return {k: v for k, v in rules.items() if v.get("enabled", True)}
    except Exception as e:
        # Si falla, retornar diccionario vacío (fallback a hardcoded)
        return {}

'''

def make_backup():
    """Crea un backup del script original."""
    backup_path = Path(str(SCRIPT_PATH) + BACKUP_SUFFIX)
    print(f"📦 Creando backup en: {backup_path}")
    
    if not SCRIPT_PATH.exists():
        print(f"❌ Error: No se encontró el script en {SCRIPT_PATH}")
        return None
    
    content = SCRIPT_PATH.read_text()
    backup_path.write_text(content)
    print(f"✅ Backup creado exitosamente")
    return backup_path


def insert_load_custom_rules_function(content):
    """Inserta la función load_custom_validation_rules después de load_validation_rules."""
    # Buscar el final de la función load_validation_rules
    pattern = r'(def load_validation_rules\(\):.*?return \{[^}]+\}[^}]+\})'
    
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        print("⚠️  No se encontró la función load_validation_rules")
        return content
    
    # Verificar si ya existe la función
    if 'def load_custom_validation_rules' in content:
        print("ℹ️  La función load_custom_validation_rules ya existe, saltando...")
        return content
    
    # Insertar después de load_validation_rules
    end_pos = match.end()
    new_content = content[:end_pos] + '\n' + LOAD_CUSTOM_RULES_FUNCTION + content[end_pos:]
    
    print("✅ Función load_custom_validation_rules insertada")
    return new_content


def modify_work_item_validation(content):
    """Modifica la validación de work item para usar regla configurable."""
    # Buscar la validación hardcoded
    old_code = r'''    if not title_has_work_item\(title\):
        verdict = "rechazar"
        reasons\.append\("título sin work item claro"\)'''
    
    new_code = '''    # Cargar reglas personalizadas una sola vez
    custom_rules = load_custom_validation_rules()
    
    # Validar título con regla configurable
    work_item_rule = custom_rules.get("work_item_validation")
    if work_item_rule:
        pattern = work_item_rule.get("pattern", "")
        if pattern and not re.search(pattern, title or "", re.IGNORECASE):
            verdict = "rechazar"
            reasons.append(work_item_rule.get("error_message", "título sin work item claro"))
    elif not title_has_work_item(title):
        # Fallback a validación hardcoded si no existe la regla
        verdict = "rechazar"
        reasons.append("título sin work item claro")'''
    
    if re.search(old_code, content):
        content = re.sub(old_code, new_code, content)
        print("✅ Validación de work item modificada")
    else:
        print("⚠️  No se encontró la validación de work item hardcoded")
    
    return content


def modify_markdown_validation(content):
    """Modifica la validación de archivos .md para usar regla configurable."""
    old_code = r'''    if any\(\(p or ""\)\.endswith\("\.md"\) for p in paths\):
        warnings\.append\("contiene archivo \.md — revisar si hay tarea manual pendiente"\)'''
    
    new_code = '''    # Validar archivos .md con regla configurable
    md_rule = custom_rules.get("markdown_files_warning")
    if md_rule and any((p or "").endswith(".md") for p in paths):
        msg = md_rule.get("error_message", "contiene archivo .md — revisar si hay tarea manual pendiente")
        if md_rule.get("severity") == "error":
            verdict = "rechazar"
            reasons.append(msg)
        else:
            warnings.append(msg)
    elif any((p or "").endswith(".md") for p in paths):
        # Fallback
        warnings.append("contiene archivo .md — revisar si hay tarea manual pendiente")'''
    
    if re.search(old_code, content):
        content = re.sub(old_code, new_code, content)
        print("✅ Validación de archivos .md modificada")
    else:
        print("⚠️  No se encontró la validación de archivos .md hardcoded")
    
    return content


def modify_deployment_sequence_validation(content):
    """Modifica la validación de deployment sequence para usar regla configurable."""
    old_code = r'''                        if not yaml_in_deploy_sequence\(target_ref, release_key, datatype\):
                            verdict = "rechazar"
                            reasons\.append\(f"dataPack \{datatype\}\.yaml no está en el deploy sequence"\)'''
    
    new_code = '''                        # Validar deployment sequence con regla configurable
                        deploy_seq_rule = custom_rules.get("deployment_sequence_validation")
                        if deploy_seq_rule:
                            if not yaml_in_deploy_sequence(target_ref, release_key, datatype):
                                msg = deploy_seq_rule.get("error_message", "dataPack YAML no está en el deploy sequence")
                                if deploy_seq_rule.get("severity") == "error":
                                    verdict = "rechazar"
                                    reasons.append(f"{msg} ({datatype}.yaml)")
                                else:
                                    warnings.append(f"{msg} ({datatype}.yaml)")
                        elif not yaml_in_deploy_sequence(target_ref, release_key, datatype):
                            # Fallback
                            verdict = "rechazar"
                            reasons.append(f"dataPack {datatype}.yaml no está en el deploy sequence")'''
    
    if re.search(old_code, content):
        content = re.sub(old_code, new_code, content)
        print("✅ Validación de deployment sequence modificada")
    else:
        print("⚠️  No se encontró la validación de deployment sequence hardcoded")
    
    return content


def verify_syntax(script_path):
    """Verifica la sintaxis del script modificado."""
    import subprocess
    
    print("🔍 Verificando sintaxis...")
    result = subprocess.run(
        ["python3", "-m", "py_compile", str(script_path)],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print("✅ Sintaxis correcta")
        return True
    else:
        print(f"❌ Error de sintaxis:\n{result.stderr}")
        return False


def main():
    print("🔄 Iniciando migración a reglas configurables...\n")
    
    # 1. Hacer backup
    backup_path = make_backup()
    if not backup_path:
        return 1
    
    # 2. Leer contenido original
    content = SCRIPT_PATH.read_text()
    
    # 3. Aplicar modificaciones
    print("\n📝 Aplicando modificaciones...")
    content = insert_load_custom_rules_function(content)
    content = modify_work_item_validation(content)
    content = modify_markdown_validation(content)
    content = modify_deployment_sequence_validation(content)
    
    # 4. Guardar cambios
    print("\n💾 Guardando cambios...")
    SCRIPT_PATH.write_text(content)
    
    # 5. Verificar sintaxis
    print()
    if not verify_syntax(SCRIPT_PATH):
        print("\n❌ Error en la migración, restaurando backup...")
        SCRIPT_PATH.write_text(backup_path.read_text())
        return 1
    
    print(f"\n✅ ¡Migración completada exitosamente!")
    print(f"📝 Backup guardado en: {backup_path}")
    print(f"\n📋 Próximos pasos:")
    print(f"   1. Probar con PRs de prueba")
    print(f"   2. Verificar que las reglas configurables se apliquen")
    print(f"   3. Monitorear logs por 24h")
    print(f"\n💡 Para revertir: cp {backup_path} {SCRIPT_PATH}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
