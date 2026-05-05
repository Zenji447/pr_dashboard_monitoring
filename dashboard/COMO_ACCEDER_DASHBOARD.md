# 🚀 Cómo Acceder al Dashboard Multi-Tenant

## 📋 Pasos para Acceder

### 1. **Abrir el Dashboard**
```
http://localhost:5000
```

### 2. **Configurar API Key (Primera vez)**
Cuando abras el dashboard por primera vez, verás un **modal de configuración** que dice:

```
🔑 Configurar API Key

Para acceder al dashboard, necesitas configurar tu API Key de tenant.

API Key del tenant existente:
prm_AoHXVfu7N1fO44X5snd57vHGpXiudWJKNTecJhJgBmo

[Campo de texto con la API Key ya pre-llenada]

[Botón: Configurar]
```

### 3. **Hacer Clic en "Configurar"**
- La API Key ya está pre-llenada
- Solo haz clic en **"Configurar"**
- La página se recargará automáticamente

### 4. **¡Ya Puedes Ver el Dashboard!**
Después de configurar la API Key, verás:
- ⚡ **Activos** - PRs activos
- ✅ **Hoy** - PRs completados hoy
- 📅 **Ayer** - PRs completados ayer
- 🗓 **Por rango** - PRs por fecha
- 📋 **Historial** - Historial completo
- ⚙️ **Reglas** - Gestión de reglas
- 🌿 **Ramas** - Gestión de ramas
- 👥 **Administración** - ¡Tu nuevo panel de tenants!

### 5. **Ir al Panel de Administración**
- Haz clic en el tab **"👥 Administración"**
- Verás tu panel de gestión de tenants

---

## 🎯 Lo que Verás en Administración

### 📊 **Resumen (KPIs)**
```
┌─────────────────┬─────────────────┬─────────────────┬─────────────────┐
│ Total Clientes  │    Activos      │   Enterprise    │ Integraciones   │
│       1         │       1         │       1         │       2         │
└─────────────────┴─────────────────┴─────────────────┴─────────────────┘
```

### 📋 **Tabla de Tenants**
```
┌────┬─────────────────────┬──────────────┬────────────┬─────────────┬──────────────┬─────────┬──────────┐
│ ID │      Empresa        │  Subdominio  │    Plan    │ Azure DevOps│ Integraciones│ Estado  │ Acciones │
├────┼─────────────────────┼──────────────┼────────────┼─────────────┼──────────────┼─────────┼──────────┤
│ 1  │ Salesforce Mexico   │ salesforce-mx│ ENTERPRISE │ SalesForce  │      2       │✓ Activo │ ✏️ 🗑️   │
└────┴─────────────────────┴──────────────┴────────────┴─────────────┴──────────────┴─────────┴──────────┘
```

### 🎮 **Botones Disponibles**
- **↻ Recargar** - Actualiza la lista
- **➕ Nuevo Cliente** - Crear nuevo tenant
- **✏️ Editar** - Modificar tenant existente
- **🗑️ Eliminar** - Eliminar tenant

---

## 🔧 Crear Nuevo Cliente (Ejemplo)

1. **Hacer clic en "➕ Nuevo Cliente"**
2. **Llenar el formulario**:
   ```
   Nombre Empresa: Acme Corporation
   Subdominio: acme-corp
   Plan: Enterprise
   
   Azure DevOps:
   URL: https://dev.azure.com/acme-org
   Proyecto: AcmeProject
   Repositorio: AcmeRepo
   
   Integraciones:
   ☑️ Slack - Canal: C123456789
   ☑️ Google Sheets - ID: 1ABC123...
   ```
3. **Hacer clic en "Crear Cliente"**
4. **Copiar la API Key generada**

---

## 🚨 Si No Ves Nada

### **Opción 1: Limpiar Cache del Navegador**
1. Presiona `Ctrl + Shift + R` (o `Cmd + Shift + R` en Mac)
2. Esto recarga la página sin cache

### **Opción 2: Abrir en Ventana Incógnita**
1. Abre una ventana incógnita/privada
2. Ve a `http://localhost:5000`
3. Configura la API Key nuevamente

### **Opción 3: Verificar Consola del Navegador**
1. Presiona `F12` para abrir DevTools
2. Ve a la pestaña "Console"
3. Busca errores en rojo
4. Compárteme cualquier error que veas

### **Opción 4: Verificar que el Servidor Esté Funcionando**
```bash
curl http://localhost:5000/health
# Debería responder: {"ok":true,"status":"healthy",...}
```

---

## 📱 Acceso Directo

Si quieres saltarte el modal de configuración, puedes configurar la API Key manualmente:

1. **Abrir DevTools** (`F12`)
2. **Ir a Console**
3. **Ejecutar**:
   ```javascript
   localStorage.setItem('pr_dashboard_api_key', 'prm_AoHXVfu7N1fO44X5snd57vHGpXiudWJKNTecJhJgBmo');
   location.reload();
   ```

---

## 🎉 ¡Listo!

Una vez que configures la API Key, tendrás acceso completo a:
- ✅ Dashboard de PRs
- ✅ Gestión de reglas
- ✅ Gestión de ramas  
- ✅ **Panel de administración de tenants**

**¡Tu SaaS multi-tenant está funcionando perfectamente!** 🚀

---

**URL**: http://localhost:5000  
**API Key**: `prm_AoHXVfu7N1fO44X5snd57vHGpXiudWJKNTecJhJgBmo`