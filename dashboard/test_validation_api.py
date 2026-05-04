#!/usr/bin/env python3
"""
Script de prueba para verificar la API de validaciones de PR
"""

import sys
from pathlib import Path

# Agregar el directorio actual al path
sys.path.insert(0, str(Path(__file__).parent))

from integrations.state import load_pr_validation_rules, save_pr_validation_rules

def test_load_rules():
    """Prueba cargar las reglas de validación"""
    print("🔍 Cargando reglas de validación...")
    rules = load_pr_validation_rules()
    
    print("\n📋 Reglas actuales:")
    for target, rule in rules.items():
        print(f"\n  • {target}:")
        for key, value in rule.items():
            print(f"    - {key}: {value}")
    
    return rules

def test_save_rules():
    """Prueba guardar reglas de validación"""
    print("\n💾 Probando guardar reglas...")
    
    test_rules = {
        "develop": {
            "release_pattern": r"r?6[.\-]1",
            "release_message": "PR hacia develop sin release r6.1 en rama fuente",
            "sprint": "sp70",
            "sprint_message": "PR hacia develop sin sprint sp70 en rama fuente",
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
    
    save_pr_validation_rules(test_rules)
    print("✅ Reglas guardadas correctamente")
    
    # Verificar que se guardaron
    loaded = load_pr_validation_rules()
    if loaded == test_rules:
        print("✅ Verificación exitosa: las reglas se guardaron correctamente")
    else:
        print("❌ Error: las reglas no coinciden")
        return False
    
    return True

def main():
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║        TEST: API de Validaciones de PR                      ║")
    print("╚══════════════════════════════════════════════════════════════╝\n")
    
    try:
        # Test 1: Cargar reglas
        rules = test_load_rules()
        
        # Test 2: Guardar reglas
        if test_save_rules():
            print("\n✅ Todos los tests pasaron correctamente")
            print("\n📊 Resumen:")
            print(f"  - Ramas configuradas: {len(rules)}")
            print(f"  - Sprint actual (develop): {rules.get('develop', {}).get('sprint', 'N/A')}")
            return 0
        else:
            print("\n❌ Algunos tests fallaron")
            return 1
            
    except Exception as e:
        print(f"\n❌ Error durante los tests: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
