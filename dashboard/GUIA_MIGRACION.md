# 🎯 Guía Paso a Paso: Migración a Multi-Tenant

## 📍 Estás aquí

```
✅ Rama: feature/saas-multi-tenant
✅ Archivos creados:
   - migrations/001_create_multi_tenant_schema.sql
   - migrations/migrate_to_multi_tenant.py
   - migrations/README.md
```

---

## 🚀 Paso 1: Detener el Servidor

**¿Por qué?** Para que no haya conflictos con la base de datos.

```bash
# Ve a la terminal donde corre el servidor (terminal 3)
# Presiona: Ctrl + C
```

**Verifica que se detuvo:**
```bash
# Deberías ver algo como:
# ^C
# Keyboard interrupt received, exiting.
```

---

## 🚀 Paso 2: Ejecutar la Migración

**Desde la terminal, en la carpeta del proyecto:**

```bash
python3 migrations/migrate_to_multi_tenant.py
```

**Verás algo como esto:**

```
======================================================================
🚀 MIGRACIÓN A MULTI-TENANT
======================================================================

📦 Paso 1: Creando backup de seguridad...
✅ Backup creado: ../memoria/state_backup_20260505_124500.db

📋 Paso 2: Creando nuevas tablas...
✅ Migración SQL completada
   Tablas creadas: tenants, tenant_azure_config, tenant_integrations, ...

👤 Paso 3: Creando tu tenant...
✅ Tenant creado con ID: 1
   API Key: prm_xxxxxxxxxxxxxxxxxxxxxxxxxxx
   ⚠️  GUARDA ESTA API KEY - La necesitarás para configurar el .env

✅ Configuración de Azure DevOps creada
✅ Integración de Slack configurada
✅ Integración de Google Sheets configurada
✅ Configuración general creada

📦 Paso 4: Migrando datos existentes...
✅ Datos migrados correctamente

📝 Paso 5: Actualizando configuración...
✅ Archivo .env actualizado

🔍 Paso 6: Verificando migración...
✅ Tenants creados: 1
✅ Configuraciones de Azure: 1
✅ Integraciones configuradas: 2
✅ Planes disponibles: 3

======================================================================
✅ MIGRACIÓN COMPLETADA
======================================================================

📊 Resumen:
   • Tenant ID: 1
   • Subdomain: salesforce-mx
   • Company: Salesforce Mexico
   • Plan: enterprise
   • API Key: prm_xxxxxxxxxxxxxxxxxxxxxxxxxxx

⚠️  IMPORTANTE:
   1. Guarda la API Key en un lugar seguro
   2. Reinicia el servidor: python3 app.py
   3. Verifica que todo funciona correctamente
   4. El backup está en: ../memoria/state_backup_*.db
```

---

## 🚀 Paso 3: Guardar la API Key

**MUY IMPORTANTE:** Copia la API Key que te muestra el script.

```bash
# Ejemplo:
API Key: prm_abc123def456ghi789jkl012mno345pqr678stu901vwx234yz
```

**¿Dónde está guardada?**
- Ya está en tu archivo `.env` automáticamente
- Pero guárdala también en un lugar seguro (notas, password manager)

---

## 🚀 Paso 4: Verificar el archivo .env

```bash
cat .env
```

**Deberías ver algo como:**

```bash
# Configuración existente...
AZURE_DEVOPS_PAT="tu_token_azure"
SLACK_BOT_TOKEN="xoxb-..."

# Multi-Tenant Configuration (NUEVO)
API_KEY="prm_xxxxxxxxxxxxxxxxxxxxxxxxxxx"
TENANT_ID="1"
TENANT_SUBDOMAIN="salesforce-mx"
```

---

## 🚀 Paso 5: Reiniciar el Servidor

```bash
python3 app.py
```

**Deberías ver:**

```
2026-05-05 12:45:00 [INFO] pr_dashboard: Iniciando servidor...
 * Running on http://127.0.0.1:5000
 * Running on http://192.168.x.x:5000
```

---

## 🚀 Paso 6: Probar que Funciona

1. **Abre tu navegador:**
   ```
   http://localhost:5000
   ```

2. **Deberías ver:**
   - ✅ Tu dashboard normal
   - ✅ Todos tus PRs
   - ✅ Todas tus configuraciones
   - ✅ Todo funcionando igual que antes

3. **Verifica las configuraciones:**
   - Ve al tab "⚙️ Reglas"
   - Ve al tab "🌿 Ramas"
   - Todo debería estar como lo dejaste

---

## ✅ ¡Listo! ¿Qué cambió?

### Visualmente: NADA
- Tu dashboard se ve igual
- Funciona igual
- Tus datos están intactos

### Internamente: TODO
- Ahora tienes una estructura multi-tenant
- Tus datos están asociados al "Tenant 1"
- La base de datos está lista para múltiples clientes
- Puedes agregar nuevos tenants cuando quieras

---

## 🎯 Próximos Pasos (después de verificar)

Una vez que confirmes que todo funciona:

1. **Hacer commit de los cambios:**
   ```bash
   git add migrations/
   git add GUIA_MIGRACION.md
   git commit -m "✨ Migración 001: Esquema multi-tenant implementado
   
   - Creadas tablas de tenants
   - Migrados datos actuales al primer tenant
   - Sistema listo para múltiples clientes"
   ```

2. **Siguiente fase:**
   - Modificar el código para usar las nuevas tablas
   - Implementar middleware de identificación de tenant
   - Crear UI de administración de tenants

---

## 🆘 Si Algo Sale Mal

### Problema: El servidor no inicia

**Solución:**
```bash
# Ver el error completo
python3 app.py

# Si hay error de base de datos, restaurar backup:
cp ../memoria/state_backup_*.db ../memoria/state.db
```

### Problema: No veo mis datos

**Solución:**
```bash
# Verificar que la migración se completó
sqlite3 ../memoria/state.db "SELECT * FROM tenants;"

# Deberías ver tu tenant
```

### Problema: Error de API Key

**Solución:**
```bash
# Verificar que está en .env
grep API_KEY .env

# Si no está, agrégala manualmente:
echo 'API_KEY="tu_api_key_aqui"' >> .env
```

### Problema: Quiero volver atrás

**Solución:**
```bash
# Restaurar backup
cp ../memoria/state_backup_YYYYMMDD_HHMMSS.db ../memoria/state.db

# Volver a la rama estable
git checkout stable-work

# Reiniciar servidor
python3 app.py
```

---

## 📊 Verificación Final

Ejecuta estos comandos para verificar que todo está bien:

```bash
# 1. Verificar que el servidor corre
curl http://localhost:5000/health

# 2. Verificar tenants en la base de datos
sqlite3 ../memoria/state.db "SELECT id, company_name, plan, status FROM tenants;"

# 3. Verificar configuración de Azure
sqlite3 ../memoria/state.db "SELECT tenant_id, org_url, project FROM tenant_azure_config;"

# 4. Verificar integraciones
sqlite3 ../memoria/state.db "SELECT tenant_id, integration_type, enabled FROM tenant_integrations;"
```

**Resultados esperados:**
```
# health
{"ok":true,"status":"healthy","ts":"2026-05-05T..."}

# tenants
1|Salesforce Mexico|enterprise|active

# azure_config
1|https://dev.azure.com/salesforce-mx|SalesForce

# integrations
1|slack|1
1|sheets|1
```

---

## 🎉 ¡Felicidades!

Si llegaste hasta aquí y todo funciona:

✅ Has migrado exitosamente a multi-tenant  
✅ Tu aplicación está lista para escalar  
✅ Puedes empezar a agregar nuevos clientes  
✅ Estás un paso más cerca de tu SaaS  

---

**¿Listo para ejecutar?** 🚀

Empieza por el **Paso 1: Detener el Servidor**
