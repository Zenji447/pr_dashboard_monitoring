"""
Sistema de Contexto de Tenant
==============================

Este módulo maneja la identificación y acceso a la configuración del tenant actual.
Cada petición HTTP identifica su tenant mediante la API Key.
"""

import json
import sqlite3
import threading
from contextvars import ContextVar
from pathlib import Path
from typing import Optional, Dict, Any

# Path a la base de datos
_DB_PATH = Path(__file__).parent.parent.parent / "memoria" / "state.db"

# Variable de contexto para el tenant actual (thread-safe)
_current_tenant_id: ContextVar[Optional[int]] = ContextVar('current_tenant_id', default=None)

# Cache de tenants (para no consultar la BD en cada petición)
_tenant_cache: Dict[str, 'Tenant'] = {}
_cache_lock = threading.Lock()


class TenantNotFoundError(Exception):
    """Se lanza cuando no se encuentra un tenant."""
    pass


class Tenant:
    """
    Representa un tenant (cliente) con toda su configuración.
    """
    
    def __init__(self, tenant_id: int, data: Dict[str, Any]):
        self.id = tenant_id
        self.subdomain = data.get('subdomain')
        self.company_name = data.get('company_name')
        self.api_key = data.get('api_key')
        self.plan = data.get('plan')
        self.status = data.get('status')
        
        # Configuraciones cargadas bajo demanda
        self._azure_config = None
        self._integrations = None
        self._settings = None
    
    @property
    def azure_config(self):
        """Configuración de Azure DevOps del tenant."""
        if self._azure_config is None:
            self._azure_config = self._load_azure_config()
        return self._azure_config
    
    @property
    def integrations(self):
        """Integraciones del tenant (Slack, Sheets, etc.)."""
        if self._integrations is None:
            self._integrations = self._load_integrations()
        return self._integrations
    
    @property
    def settings(self):
        """Configuración general del tenant."""
        if self._settings is None:
            self._settings = self._load_settings()
        return self._settings
    
    def _load_azure_config(self) -> Dict[str, Any]:
        """Carga la configuración de Azure DevOps desde la BD."""
        conn = sqlite3.connect(str(_DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        row = cursor.execute(
            "SELECT * FROM tenant_azure_config WHERE tenant_id = ?",
            (self.id,)
        ).fetchone()
        
        conn.close()
        
        if not row:
            raise TenantNotFoundError(f"Azure config not found for tenant {self.id}")
        
        return {
            'org_url': row['org_url'],
            'project': row['project'],
            'repository': row['repository'],
            'pat_token': row['pat_token']
        }
    
    def _load_integrations(self) -> Dict[str, Any]:
        """Carga las integraciones del tenant desde la BD."""
        conn = sqlite3.connect(str(_DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        rows = cursor.execute(
            "SELECT * FROM tenant_integrations WHERE tenant_id = ?",
            (self.id,)
        ).fetchall()
        
        conn.close()
        
        integrations = {}
        for row in rows:
            integrations[row['integration_type']] = {
                'enabled': bool(row['enabled']),
                'config': json.loads(row['config'])
            }
        
        return integrations
    
    def _load_settings(self) -> Dict[str, Any]:
        """Carga la configuración general del tenant desde la BD."""
        conn = sqlite3.connect(str(_DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        row = cursor.execute(
            "SELECT * FROM tenant_settings WHERE tenant_id = ?",
            (self.id,)
        ).fetchone()
        
        conn.close()
        
        if not row:
            # Configuración por defecto si no existe
            return {
                'language': 'es',
                'timezone': 'America/Mexico_City',
                'blocked_authors': [],
                'blocked_branches': [],
                'local_repo_path': None
            }
        
        return {
            'language': row['language'],
            'timezone': row['timezone'],
            'blocked_authors': json.loads(row['blocked_authors'] or '[]'),
            'blocked_branches': json.loads(row['blocked_branches'] or '[]'),
            'local_repo_path': row['local_repo_path'],
            'logo_url': row['logo_url'],
            'primary_color': row['primary_color']
        }
    
    def get_integration(self, integration_type: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene una integración específica.
        
        Args:
            integration_type: Tipo de integración ('slack', 'sheets', etc.)
        
        Returns:
            Dict con 'enabled' y 'config', o None si no existe
        """
        return self.integrations.get(integration_type)
    
    def has_integration(self, integration_type: str) -> bool:
        """Verifica si el tenant tiene una integración habilitada."""
        integration = self.get_integration(integration_type)
        return integration is not None and integration['enabled']
    
    def __repr__(self):
        return f"<Tenant {self.id}: {self.company_name} ({self.subdomain})>"


def get_tenant_by_api_key(api_key: str) -> Optional[Tenant]:
    """
    Obtiene un tenant por su API Key.
    
    Args:
        api_key: API Key del tenant
    
    Returns:
        Objeto Tenant o None si no se encuentra
    """
    if not api_key:
        return None
    
    # Verificar cache primero
    with _cache_lock:
        if api_key in _tenant_cache:
            return _tenant_cache[api_key]
    
    # Consultar base de datos
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    row = cursor.execute(
        "SELECT * FROM tenants WHERE api_key = ? AND status = 'active'",
        (api_key,)
    ).fetchone()
    
    conn.close()
    
    if not row:
        return None
    
    # Crear objeto Tenant
    tenant_data = {
        'subdomain': row['subdomain'],
        'company_name': row['company_name'],
        'api_key': row['api_key'],
        'plan': row['plan'],
        'status': row['status']
    }
    
    tenant = Tenant(row['id'], tenant_data)
    
    # Guardar en cache
    with _cache_lock:
        _tenant_cache[api_key] = tenant
    
    return tenant


def get_tenant_by_id(tenant_id: int) -> Optional[Tenant]:
    """
    Obtiene un tenant por su ID.
    
    Args:
        tenant_id: ID del tenant
    
    Returns:
        Objeto Tenant o None si no se encuentra
    """
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    row = cursor.execute(
        "SELECT * FROM tenants WHERE id = ? AND status = 'active'",
        (tenant_id,)
    ).fetchone()
    
    conn.close()
    
    if not row:
        return None
    
    tenant_data = {
        'subdomain': row['subdomain'],
        'company_name': row['company_name'],
        'api_key': row['api_key'],
        'plan': row['plan'],
        'status': row['status']
    }
    
    return Tenant(row['id'], tenant_data)


def set_current_tenant(tenant: Tenant):
    """
    Establece el tenant actual para el contexto de ejecución.
    
    Args:
        tenant: Objeto Tenant a establecer como actual
    """
    _current_tenant_id.set(tenant.id if tenant else None)


def get_current_tenant() -> Optional[Tenant]:
    """
    Obtiene el tenant actual del contexto de ejecución.
    
    Returns:
        Objeto Tenant actual o None si no hay tenant establecido
    """
    tenant_id = _current_tenant_id.get()
    if tenant_id is None:
        return None
    
    return get_tenant_by_id(tenant_id)


def clear_tenant_cache():
    """Limpia el cache de tenants (útil para testing o después de cambios)."""
    with _cache_lock:
        _tenant_cache.clear()


def require_tenant():
    """
    Decorator para funciones que requieren un tenant activo.
    
    Ejemplo:
        @require_tenant()
        def my_function():
            tenant = get_current_tenant()
            # ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            tenant = get_current_tenant()
            if tenant is None:
                raise TenantNotFoundError("No tenant in current context")
            return func(*args, **kwargs)
        return wrapper
    return decorator
