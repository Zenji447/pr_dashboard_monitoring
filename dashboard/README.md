# PR Dashboard — Multi-Tenant SaaS

Dashboard para monitoreo y auto-aprobación de Pull Requests en Azure DevOps con integración a Slack y Google Sheets.

## 🎉 Actualización: Sistema Multi-Tenant

**Fecha**: 6 de Mayo, 2026

✅ **Sistema de testing completo implementado**
- 88 tests automatizados pasando (100%)
- 92% de cobertura de código
- Property-based testing con Hypothesis
- Thread-safety verificado
- Soporte para múltiples clientes/tenants

👉 **Documentación completa**: Ver `INDICE_DOCUMENTACION.md`  
👉 **Inicio rápido**: Ver `LEEME_PRIMERO.md`

---

## 🚀 Características

### Multi-Tenant
- ✅ Soporte para múltiples clientes
- ✅ Configuración aislada por tenant
- ✅ API Key única por cliente
- ✅ Panel de administración web

### Dashboard de PRs
- ✅ Visualización de Pull Requests
- ✅ Auto-aprobación configurable
- ✅ Reglas de validación personalizables
- ✅ Gestión dinámica de ramas

### Integraciones
- ✅ Azure DevOps (PRs, repositorios)
- ✅ Slack (notificaciones)
- ✅ Google Sheets (exportación)

---

## Setup

### 1. Instalar dependencias

```bash
pip3 install flask google-api-python-client google-auth python-dotenv
```

### 2. Configurar variables de entorno

Copia `.env.example` a `.env` y completa los valores:

```bash
cp .env.example .env
```

Edita `.env` con tus credenciales:

```env
# Azure DevOps
AZURE_ORG=TuOrganizacion
AZURE_PROJECT=TuProyecto
AZURE_REPOSITORY=TuRepo

# Slack
SLACK_TOKEN=xoxp-tu-token-aqui
SLACK_PR_CHANNEL=C123456789

# Google Sheets
GOOGLE_SHEET_ID=tu-sheet-id-aqui
GOOGLE_CREDS_PATH=../memoria/service-account-key.json

# API Security
API_KEY=tu-clave-secreta-aqui
```

### 3. Credenciales de Google

Coloca tu archivo de service account en `../memoria/service-account-key.json` o actualiza `GOOGLE_CREDS_PATH` en `.env`.

### 4. Ejecutar

```bash
cd dashboard
python3 app.py
```

El dashboard estará disponible en `http://localhost:5000`

## Funcionalidades

- ✅ Auto-aprobación configurable por rama
- 🚫 Bloqueo de autores y ramas (freeze)
- 📊 Exportación a Google Sheets
- 💬 Notificaciones a Slack
- 🔍 Validación de PRs (work items, manifests, deploy sequence)
- 🌐 Soporte multiidioma (ES/EN)

## Estructura

```
dashboard/
├── app.py              # Backend Flask
├── templates/
│   └── index.html      # Frontend
├── .env                # Configuración (no commitear)
└── .env.example        # Plantilla de configuración

scripts/
└── check_salesforce_prs.py  # Lógica de validación

memoria/
├── auto_approve_config.json
├── blocked_authors.json
└── blocked_branches.json
```

## Seguridad

- **Nunca commitees** el archivo `.env` — contiene credenciales
- El `.env.example` es solo plantilla sin valores reales
- Usa `API_KEY` para proteger endpoints de acción
