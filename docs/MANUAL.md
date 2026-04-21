# Manual del Sistema – PR Dashboard Salesforce

## ¿Qué es esto?

Dashboard web local que automatiza la revisión, aprobación y seguimiento de Pull Requests del repositorio **SalesForce** en Azure DevOps (OrgClaroColombia). Elimina la necesidad de entrar manualmente a Azure DevOps para cada acción rutinaria.

Adicionalmente, registra automáticamente cada PR completado en un **Google Sheet** con KPIs de tiempos y estado de despliegue.

---

## Arquitectura

```
Trabajo_Diario/
├── dashboard/
│   ├── app.py              # Servidor Flask (backend + API)
│   └── templates/
│       └── index.html      # Interfaz web (frontend)
├── scripts/
│   └── check_salesforce_prs.py   # Lógica de clasificación de PRs
├── memoria/
│   ├── auto_approve_config.json  # Config de auto-aprobación
│   └── blocked_authors.json      # Autores bloqueados
├── .env                    # SLACK_TOKEN
├── google_credentials.json # Service account de Google Cloud
├── Dockerfile              # Imagen Docker
├── docker-compose.yml      # Orquestación del contenedor
└── requirements.txt        # Dependencias Python
```

**Stack:** Python 3.12 · Flask · Azure CLI (`az`) · Slack API · Google Sheets API · Docker

---

## Requisitos

- `az` CLI autenticado (`az login`)
- `az devops` extension instalada
- Token de Slack en `.env` con formato:
  ```
  SLACK_TOKEN=xoxp-...
  ```
- `google_credentials.json` en `~/Desktop/Trabajo_Diario/` (service account de GCP)
- Python 3.12 o Docker

---

## Cómo correrlo

### Local
```bash
pip install -r ~/Desktop/Trabajo_Diario/requirements.txt --break-system-packages
cd ~/Desktop/Trabajo_Diario/dashboard
python3 app.py
# Abre http://localhost:5000
```

### Docker
```bash
cd ~/Desktop/Trabajo_Diario
docker-compose up --build
# Abre http://localhost:5000
```

> El contenedor monta `~/.azure` como solo lectura para usar las credenciales de `az login` del host.

---

## Interfaz – Pestañas

| Pestaña | Descripción |
|---|---|
| **Activos** | PRs activos hacia `develop`, `develop-pr` y `releaseproyecto/r6` |
| **Completados hoy** | PRs cerrados en el día actual (UTC) |
| **Completados ayer** | PRs cerrados el día anterior |
| **Por rango** | PRs cerrados entre dos fechas a elección |

El dashboard se **auto-actualiza cada 60 segundos**.

---

## Veredictos

Cada PR activo recibe un veredicto automático basado en análisis del código:

| Veredicto | Color | Significado |
|---|---|---|
| **aprobable** | 🟢 Verde | PR cumple todas las reglas, listo para aprobar |
| **aprobable con cautela** | 🟡 Amarillo | Tiene advertencias menores, revisar antes de aprobar |
| **posible aprobación** | 🔵 Azul claro | Checks del pipeline aún corriendo |
| **evaluar check** | 🟠 Naranja | Algún check/política falló |
| **revisar** | 🔵 Azul | Requiere revisión manual |
| **rechazar** | 🔴 Rojo | Incumple reglas críticas |
| **resolver conflicto** | 🟣 Morado | Tiene conflictos de merge |

### Reglas de rechazo automático
- Título sin work item (BUG/HU/HDU + número)
- PR hacia `develop` sin release `r6.1` en la rama fuente
- PR hacia `develop` sin sprint `sp69` en la rama fuente
- Componente `force-app` nuevo sin `package-metadata.xml` ni en manifest destino
- Componente `dataPack` no encontrado en manifest base del release
- Componentes duplicados en archivos YAML del PR

### Advertencias (no rechazan)
- Target `develop-pr` (rama bugfix flexible)
- PR contiene archivo `.md` → indica posible tarea manual pendiente
- dataPack validado contra manifest (informativo)

---

## Acciones por PR

### ✓ Aprobar
- Vota `approve` en Azure DevOps
- Notifica en el hilo del PR en Slack: `✅ Aprobado`
- Si el TA aún no aprobó → menciona al TA pendiente en Slack
- Si el TA ya aprobó → completa el PR automáticamente

### ⚡ Completar
- Cambia el estado del PR a `completed` en Azure DevOps
- Notifica en el hilo del PR en Slack: `🚀 Completado`
- Registra automáticamente el PR en Google Sheets
- Inicia polling de deploy en background

### ✗ Rechazar
- Solicita motivo (prompt en pantalla)
- Vota `reject` y agrega comentario en el PR
- Notifica en Slack: `❌ Rechazado`

---

## Columna Deploy

Después de completar un PR, la columna **Deploy** muestra el estado del pipeline `Salesforce_Builds` (ID 3840):

| Estado | Significado |
|---|---|
| ⏳ In progress | Pipeline corriendo |
| ✅ Desplegado | Pipeline exitoso |
| ❌ Deploy fallido | Pipeline falló o fue cancelado |

Si está `In progress`, se refresca automáticamente cada 60 segundos.

---

## Google Sheets – Registro automático de KPIs

### Configuración
- **Sheet ID:** `1jsYHmGm-2eN5986bgN5jlPO86guNfWmnf980H4TsdO0`
- **Credenciales:** `~/Desktop/Trabajo_Diario/google_credentials.json`
- **Service account:** `pr-dashboard-bot@pr-dashboard-493917.iam.gserviceaccount.com`
- La hoja debe estar compartida con la service account con rol **Editor**

### Comportamiento automático
1. Cuando un PR se **completa** → se agrega una fila con todos los datos disponibles
2. Cuando el **deploy termina** → se actualiza la fila con fecha de despliegue, resultado y tiempos recalculados

### Columnas registradas

| Columna | Fuente |
|---|---|
| PR ID | Azure DevOps |
| Título | Azure DevOps |
| Autor | Azure DevOps |
| Branch destino | Azure DevOps |
| Fecha creación | Azure DevOps |
| Fecha aprobación | Threads del PR en Azure (primer voto aprobado) |
| Fecha completado | Azure DevOps |
| Fecha despliegue | Polling de Azure Pipelines (se actualiza al terminar) |
| Tiempo revisión (min) | Creación → Aprobación |
| Tiempo merge (min) | Aprobación → Completado |
| Tiempo despliegue (min) | Completado → Deploy |
| Tiempo total (min) | Creación → Deploy |
| Tenía conflictos | `mergeStatus` del PR |
| Policy status | Evaluaciones de política en Azure |
| Resultado despliegue | Estado final del pipeline (se actualiza al terminar) |
| Auto-aprobado | Si fue aprobado por el sistema automáticamente |
| Rechazado | Si el voto fue `rejected` |
| Bloqueado | Si el autor está en la lista de bloqueados |

### Exportación manual (backfill)
El botón **📊 Exportar a Sheets** en la toolbar permite exportar PRs completados de un rango de fechas seleccionado. Útil para cargar datos históricos.

---

## Auto-aprobación

Configurable desde la interfaz (toggle + selección de branches):

- Cuando está activa, aprueba automáticamente PRs con veredicto `aprobable` o `aprobable con cautela` en las branches seleccionadas
- Condiciones: sin conflictos, sin autor bloqueado, policy no fallida, sin archivos `.md`, sin razones de rechazo
- Al auto-aprobar: notifica en Slack y menciona al TA Reviewer
- Config guardada en `memoria/auto_approve_config.json`

---

## Autores bloqueados

Lista de autores cuyos PRs se muestran en el dashboard pero no reciben acciones automáticas ni notificaciones de Slack. Configurable desde la interfaz.

Config guardada en `memoria/blocked_authors.json`.

---

## TA Reviewers

Los siguientes usuarios son reconocidos como TA Reviewers. Si un PR necesita su aprobación, el sistema los menciona automáticamente en Slack:

| Nombre | Slack ID |
|---|---|
| Gustavo Alonso Muciño | U06JUHG1G9Y |
| Hugo Revuelta | U07TQ8JNMBR |
| Gabriel Alvis | U066X49C5NZ |
| Francisco Zubizarreta | U01LXV1UD3K |
| Luís Guilherme Lino | U023L6SJVQW |

---

## Canal de Slack

Todas las notificaciones van al canal con ID `C080K9D6EG2`. Los mensajes se publican **en el hilo del PR** cuando existe, o en el canal general si el PR aún no fue publicado manualmente.

---

## Ramas soportadas (PRs activos)

| Rama destino | Release key usado |
|---|---|
| `develop` | `release-06.1` |
| `develop-pr` | `release-06` |
| `releaseproyecto/r6` | `release-06` |

---

## Archivos clave

### `.env`
```
SLACK_TOKEN=xoxp-...
```

### `google_credentials.json`
Service account key de Google Cloud. No subir a git.

### `docker-compose.yml`
Monta `~/.azure` para autenticación y expone el puerto 5000.

### `scripts/check_salesforce_prs.py`
Contiene toda la lógica de clasificación: validación de títulos, análisis de archivos cambiados, búsqueda en manifests, detección de conflictos y duplicados en YAML.

---

## Solución de problemas

| Problema | Causa probable | Solución |
|---|---|---|
| `Failed to fetch` en el browser | Servidor Flask caído | Reiniciar `python3 app.py` |
| PRs no aparecen | Rama destino no soportada | Verificar que el target esté en la lista de ramas soportadas |
| Deploy siempre `—` | PR aún activo (no completado) | El deploy solo aparece después de completar el PR |
| Botón Aprobar deshabilitado | Veredicto `rechazar` o `revisar` | Revisar las razones mostradas en rojo |
| Falso positivo en manifest | Repo local desactualizado | Correr `git fetch origin` en `/home/zen6/cc/SalesForce` |
| Google Sheets 403 | Hoja no compartida con service account | Compartir con `pr-dashboard-bot@pr-dashboard-493917.iam.gserviceaccount.com` como Editor |
| `ModuleNotFoundError: google` | Dependencias no instaladas | `pip install -r requirements.txt --break-system-packages` |
