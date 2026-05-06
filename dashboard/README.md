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

---

## 🧪 Testing

### Ejecutar Tests

```bash
# Activar entorno virtual
source venv/bin/activate

# Ejecutar todos los tests
pytest tests/ -v

# Ejecutar con cobertura
pytest tests/ --cov=integrations --cov-report=html

# Ver reporte de cobertura
open htmlcov/index.html
```

### Estadísticas de Testing

- **Total Tests**: 88 pasando
- **Cobertura**: 92% (tenant_context.py)
- **Tiempo**: ~16 segundos
- **Framework**: pytest + hypothesis

---

## 📚 Documentación

### Guías de Usuario
- `LEEME_PRIMERO.md` - Inicio rápido
- `INDICE_DOCUMENTACION.md` - Índice completo
- `RESUMEN_EJECUTIVO.md` - Resumen ejecutivo

### Documentación Técnica
- `.kiro/specs/tenant-administration-system/design.md` - Arquitectura
- `.kiro/specs/tenant-administration-system/requirements.md` - Requisitos
- `.kiro/specs/tenant-administration-system/tasks.md` - Plan de tareas

### Guías de Desarrollo
- `GIT_COMMIT_INSTRUCTIONS.md` - Cómo hacer commits
- `RESUMEN_FINAL_TESTING_NOCTURNO.md` - Trabajo completado

---

## 🏗️ Arquitectura Multi-Tenant

```
┌─────────────────────────────────────────┐
│         Multi-Tenant System             │
├─────────────────────────────────────────┤
│  Tenant 1  │  Tenant 2  │  Tenant 3    │
│  (Client)  │  (Client)  │  (Client)    │
├────────────┼────────────┼──────────────┤
│  API Key   │  API Key   │  API Key     │
│  Config    │  Config    │  Config      │
│  Azure     │  Azure     │  Azure       │
│  Slack     │  Slack     │  Slack       │
└─────────────────────────────────────────┘
```

Cada tenant tiene:
- Configuración aislada de Azure DevOps
- Integraciones propias (Slack, Sheets)
- Settings personalizados
- API Key única

---

## 🔧 Desarrollo

### Estructura del Proyecto

```
dashboard/
├── app.py                  # Servidor Flask
├── integrations/           # Integraciones
│   ├── tenant_context.py   # Sistema multi-tenant
│   ├── azure.py            # Azure DevOps
│   ├── slack.py            # Slack
│   └── state.py            # Base de datos
├── services/               # Lógica de negocio
│   ├── pr_service.py       # Pull Requests
│   └── rules_service.py    # Reglas de validación
├── templates/              # Frontend
│   └── index.html          # Dashboard web
└── tests/                  # Tests automatizados
    ├── test_tenant_context_properties.py
    ├── test_tenant_crud_properties.py
    ├── test_azure_config_properties.py
    ├── test_integrations_properties.py
    └── test_settings_properties.py
```

### Tecnologías

- **Backend**: Flask (Python)
- **Base de Datos**: SQLite
- **Testing**: pytest + hypothesis
- **Frontend**: HTML + JavaScript
- **Integraciones**: Azure DevOps API, Slack API, Google Sheets API

---

## 📊 Estado del Proyecto

### Fase 1: Testing & Validación
- [x] Task 1.1: Tenant Context Tests (20 tests)
- [x] Task 1.2: Tenant CRUD Tests (19 tests)
- [x] Task 1.3: Azure Config Tests (16 tests)
- [x] Task 1.4: Integrations Tests (16 tests)
- [x] Task 1.5: Settings Tests (17 tests)
- [ ] Task 1.6: API Endpoints Tests
- [ ] Task 1.7: Middleware Tests
- [ ] Task 1.8: E2E Tests

**Progreso**: 62.5% (5/8 tareas completadas)

### Próximas Fases
- Fase 2: Seguridad (encriptación, rate limiting)
- Fase 3: Performance (cache, connection pooling)
- Fase 4: Monitoreo (logging, metrics)
- Fase 5: Documentación (guías de usuario)
- Fase 6: Migración (limpieza de código legacy)

---

## 🤝 Contribuir

1. Lee la documentación en `.kiro/specs/`
2. Ejecuta los tests: `pytest tests/ -v`
3. Crea una rama: `git checkout -b feature/nueva-funcionalidad`
4. Haz tus cambios
5. Asegúrate de que los tests pasen
6. Haz commit: Ver `GIT_COMMIT_INSTRUCTIONS.md`
7. Crea un Pull Request

---

## 📝 Licencia

[Tu licencia aquí]

---

## 📞 Soporte

Para preguntas o soporte:
1. Revisa la documentación en `INDICE_DOCUMENTACION.md`
2. Ejecuta los tests para verificar el sistema
3. Consulta los documentos de especificación en `.kiro/specs/`

---

**Última actualización**: 6 de Mayo, 2026  
**Versión**: 4.0 (Multi-Tenant)  
**Rama**: `feature/saas-multi-tenant`

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
