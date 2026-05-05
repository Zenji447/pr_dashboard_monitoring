#!/usr/bin/env python3
"""
Script de prueba para verificar el sistema de tenant context
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from integrations.tenant_context import (
    get_tenant_by_api_key,
    get_tenant_by_id,
    set_current_tenant,
    get_current_tenant
)

def test_tenant_by_id():
    """Prueba obtener tenant por ID"""
    print("🧪 Prueba 1: Obtener tenant por ID...")
    tenant = get_tenant_by_id(1)
    
    if tenant:
        print(f"✅ Tenant encontrado: {tenant}")
        print(f"   - ID: {tenant.id}")
        print(f"   - Company: {tenant.company_name}")
        print(f"   - Subdomain: {tenant.subdomain}")
        print(f"   - Plan: {tenant.plan}")
        print(f"   - Status: {tenant.status}")
        return True
    else:
        print("❌ Tenant no encontrado")
        return False


def test_tenant_by_api_key():
    """Prueba obtener tenant por API Key"""
    print("\n🧪 Prueba 2: Obtener tenant por API Key...")
    api_key = "prm_AoHXVfu7N1fO44X5snd57vHGpXiudWJKNTecJhJgBmo"
    tenant = get_tenant_by_api_key(api_key)
    
    if tenant:
        print(f"✅ Tenant encontrado por API Key")
        print(f"   - ID: {tenant.id}")
        print(f"   - Company: {tenant.company_name}")
        return True
    else:
        print("❌ Tenant no encontrado por API Key")
        return False


def test_azure_config():
    """Prueba cargar configuración de Azure"""
    print("\n🧪 Prueba 3: Cargar configuración de Azure DevOps...")
    tenant = get_tenant_by_id(1)
    
    if tenant:
        try:
            azure_config = tenant.azure_config
            print(f"✅ Configuración de Azure cargada:")
            print(f"   - Org URL: {azure_config['org_url']}")
            print(f"   - Project: {azure_config['project']}")
            print(f"   - Repository: {azure_config['repository']}")
            return True
        except Exception as e:
            print(f"❌ Error cargando config de Azure: {e}")
            return False
    else:
        print("❌ Tenant no encontrado")
        return False


def test_integrations():
    """Prueba cargar integraciones"""
    print("\n🧪 Prueba 4: Cargar integraciones...")
    tenant = get_tenant_by_id(1)
    
    if tenant:
        try:
            integrations = tenant.integrations
            print(f"✅ Integraciones cargadas:")
            for int_type, int_data in integrations.items():
                status = "✓ Habilitada" if int_data['enabled'] else "✗ Deshabilitada"
                print(f"   - {int_type}: {status}")
            return True
        except Exception as e:
            print(f"❌ Error cargando integraciones: {e}")
            return False
    else:
        print("❌ Tenant no encontrado")
        return False


def test_settings():
    """Prueba cargar configuración general"""
    print("\n🧪 Prueba 5: Cargar configuración general...")
    tenant = get_tenant_by_id(1)
    
    if tenant:
        try:
            settings = tenant.settings
            print(f"✅ Configuración general cargada:")
            print(f"   - Language: {settings['language']}")
            print(f"   - Timezone: {settings['timezone']}")
            print(f"   - Blocked Authors: {settings['blocked_authors']}")
            return True
        except Exception as e:
            print(f"❌ Error cargando settings: {e}")
            return False
    else:
        print("❌ Tenant no encontrado")
        return False


def test_context():
    """Prueba el contexto de tenant"""
    print("\n🧪 Prueba 6: Contexto de tenant...")
    tenant = get_tenant_by_id(1)
    
    if tenant:
        set_current_tenant(tenant)
        current = get_current_tenant()
        
        if current and current.id == tenant.id:
            print(f"✅ Contexto funcionando correctamente")
            print(f"   - Tenant actual: {current.company_name}")
            return True
        else:
            print("❌ Contexto no funciona")
            return False
    else:
        print("❌ Tenant no encontrado")
        return False


def main():
    print("=" * 70)
    print("🧪 PRUEBAS DEL SISTEMA MULTI-TENANT")
    print("=" * 70)
    
    results = []
    
    results.append(("Tenant por ID", test_tenant_by_id()))
    results.append(("Tenant por API Key", test_tenant_by_api_key()))
    results.append(("Azure Config", test_azure_config()))
    results.append(("Integraciones", test_integrations()))
    results.append(("Settings", test_settings()))
    results.append(("Contexto", test_context()))
    
    print("\n" + "=" * 70)
    print("📊 RESUMEN DE PRUEBAS")
    print("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    print("\n" + "=" * 70)
    print(f"Resultado: {passed}/{total} pruebas pasaron")
    
    if passed == total:
        print("🎉 ¡TODAS LAS PRUEBAS PASARON!")
        return 0
    else:
        print(f"⚠️  {total - passed} pruebas fallaron")
        return 1


if __name__ == "__main__":
    sys.exit(main())
