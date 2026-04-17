# Manual del Sistema – PR Dashboard Salesforce

## ¿Qué es esto?

Dashboard web local que automatiza la revisión, aprobación y seguimiento de Pull Requests del repositorio **SalesForce** en Azure DevOps (OrgClaroColombia). Elimina la necesidad de entrar manualmente a Azure DevOps para cada acción rutinaria.

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
├── .env                    # SLACK_TOKEN
├── Dockerfile              # Imagen Docker
├── docker-compose.yml      # Orquestación del contenedor
└── requirements.txt        # Dependencias Python
```

**Stack:** Python 3.12 · Flask · Azure CLI (`az`) · Slack API · Docker

---

## Requisitos

- `az` CLI autenticado (`az login`)
- `az devops` extension instalada
- Token de Slack en `.env` con formato:
  ```
  SLACK_TOKEN=xoxp-...
  ```
- Python 3.12 o Docker

---

## Cómo correrlo

### Local
```bash
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

El dashboard se **auto-actualiza cada 30 segundos**.

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

### Advertencias (no rechazan)
- Target `develop-pr` (rama bugfix flexible)
- PR contiene archivo `.md` → indica posible tarea manual pendiente
- dataPack validado contra manifest (informativo)

---

## Acciones por PR

### ✓ Aprobar
- Vota `approve` en Azure DevOps
- Notifica en el hilo del PR en Slack: `✅ Aprobado`
- Si el botón **Completar** sigue deshabilitado (falta aprobación del TA):
  - Verifica si algún TA Reviewer ya aprobó
  - Si ya aprobó → muestra `✅ TA aprobado`
  - Si no → espera a que el PR aparezca en el canal de Slack (polling cada 15 seg), espera 5 seg y menciona al TA pendiente: `@TA por favor aprueba este PR para poder completarlo 🙏`

### ⚡ Completar
- Cambia el estado del PR a `completed` en Azure DevOps
- Notifica en el hilo del PR en Slack: `🚀 Completado`
- Solo habilitado cuando el veredicto permite aprobación

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

Si está `In progress`, se refresca automáticamente cada 15 segundos.

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

### `docker-compose.yml`
Monta `~/.azure` para autenticación y expone el puerto 5000.

### `scripts/check_salesforce_prs.py`
Contiene toda la lógica de clasificación: validación de títulos, análisis de archivos cambiados, búsqueda en manifests, detección de conflictos.

---

## Solución de problemas

| Problema | Causa probable | Solución |
|---|---|---|
| `Failed to fetch` en el browser | Servidor Flask caído | Reiniciar `python3 app.py` |
| PRs no aparecen | Rama destino no soportada | Verificar que el target esté en la lista de ramas soportadas |
| Deploy siempre `—` | PR aún activo (no completado) | El deploy solo aparece después de completar el PR |
| Botón Aprobar deshabilitado | Veredicto `rechazar` o `revisar` | Revisar las razones mostradas en rojo |
| Falso positivo en manifest | Repo local desactualizado | Correr `git fetch origin` en `/home/zen6/cc/SalesForce` |
