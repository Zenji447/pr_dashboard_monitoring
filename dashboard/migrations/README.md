# 📦 Migraciones de Base de Datos

## 🎯 Migración 001: Multi-Tenant

Esta migración convierte tu aplicación de single-tenant a multi-tenant.

### ✅ ¿Qué hace?

1. **Crea nuevas tablas:**
   - `tenants` - Clientes del SaaS
   - `tenant_azure_config` - Configuración de Azure DevOps por cliente
   - `tenant_integrations` - Integraciones opcionales (Slack, Sheets)
   - `tenant_settings` - Configuración general por cliente
   - `tenant_users` - Usuarios por cliente (para futuro)
   - `plans` - Planes de suscripción

2. **Migra tus datos actuales:**
   - Te convierte en el primer tenant
   - Migra tu configuración de Azure DevOps
   - Migra tus integraciones de Slack y Sheets
   - Genera una API key única para ti

3. **Crea backup automático:**
   - Antes de hacer cambios, crea un backup de tu base de datos

### 🚀 Cómo ejecutar

```bash
# Desde la raíz del proyecto
python3 migrations/migrate_to_multi_tenant.py
```

### 📋 Pasos que ejecuta

```
1. 📦 Crear backup de seguridad
2. 📋 Crear nuevas tablas
3. 👤 Crear tu tenant (Salesforce Mexico)
4. 📦 Migrar datos existentes
5. 📝 Actualizar archivo .env
6. 🔍 Verificar que todo funcionó
```

### ⚠️ Importante ANTES de ejecutar

1. **Detén el servidor:**
   ```bash
   # En la terminal donde corre el servidor, presiona Ctrl+C
   ```

2. **Verifica que tienes backup:**
   - El script crea uno automáticamente
   - Pero puedes crear uno manual también:
   ```bash
   cp ../memoria/state.db ../memoria/state_backup_manual.db
   ```

3. **Asegúrate de estar en la rama correcta:**
   ```bash
   git branch
   # Debe mostrar: * feature/saas-multi-tenant
   ```

### ✅ Después de ejecutar

1. **Guarda la API Key** que te muestra el script
2. **Reinicia el servidor:**
   ```bash
   python3 app.py
   ```
3. **Verifica que funciona:**
   - Abre http://localhost:5000
   - Deberías ver tu dashboard funcionando normal

### 🔙 Si algo sale mal

1. **Restaurar backup:**
   ```bash
   cp ../memoria/state_backup_YYYYMMDD_HHMMSS.db ../memoria/state.db
   ```

2. **Volver a la versión anterior:**
   ```bash
   git checkout stable-work
   ```

### 📊 Estructura después de la migración

```
state.db
├── Tablas antiguas (se mantienen para compatibilidad)
│   ├── kv
│   └── config
│
└── Tablas nuevas (multi-tenant)
    ├── tenants
    ├── tenant_azure_config
    ├── tenant_integrations
    ├── tenant_settings
    ├── tenant_users
    └── plans
```

### 🎯 Próximos pasos

Después de esta migración, podrás:
- ✅ Agregar nuevos clientes (tenants)
- ✅ Cada cliente tendrá su propia configuración
- ✅ Aislar datos entre clientes
- ✅ Implementar planes de pago

---

## 🆘 ¿Necesitas ayuda?

Si algo no funciona:
1. Revisa el backup en `../memoria/state_backup_*.db`
2. Verifica los logs del script
3. Restaura el backup si es necesario
