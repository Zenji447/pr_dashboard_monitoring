# Arquitectura Técnica: Migración a SaaS Multi-tenant

## 🏗️ Arquitectura Actual vs Target

### Estado Actual (Monolito)
```
┌─────────────────────────────────────┐
│         Flask App (app.py)          │
│  ┌──────────┐  ┌─────────────────┐  │
│  │ Frontend │  │ Backend + Logic │  │
│  │  (HTML)  │  │   (Python)      │  │
│  └──────────┘  └─────────────────┘  │
└─────────────────────────────────────┘
         │              │
         ▼              ▼
   ┌─────────┐    ┌──────────┐
   │  Slack  │    │  Azure   │
   │   API   │    │ DevOps   │
   └─────────┘    └──────────┘
         │
         ▼
   ┌──────────┐
   │  Google  │
   │  Sheets  │
   └──────────┘
```

### Arquitectura Target (Microservicios Ligeros)
```
                    ┌──────────────┐
                    │   CDN/WAF    │
                    │  (Cloudflare)│
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │ Load Balancer│
                    └──────┬───────┘
                           │
        ┏━━━━━━━━━━━━━━━━━┻━━━━━━━━━━━━━━━━━┓
        ▼                                    ▼
┌───────────────┐                   ┌───────────────┐
│  API Gateway  │                   │  API Gateway  │
│   (FastAPI)   │                   │   (FastAPI)   │
└───────┬───────┘                   └───────┬───────┘
        │                                   │
        ├─────────────┬─────────────────────┤
        ▼             ▼                     ▼
┌──────────┐  ┌──────────┐         ┌──────────┐
│   Auth   │  │   Core   │         │ Workers  │
│ Service  │  │ Service  │         │ (Celery) │
└────┬─────┘  └────┬─────┘         └────┬─────┘
     │             │                     │
     └─────────────┼─────────────────────┘
                   ▼
          ┌────────────────┐
          │   PostgreSQL   │
          │   (Primary)    │
          └────────┬───────┘
                   │
          ┌────────▼───────┐
          │   PostgreSQL   │
          │   (Replica)    │
          └────────────────┘
                   
     ┌─────────────┴─────────────┐
     ▼                           ▼
┌──────────┐              ┌──────────┐
│  Redis   │              │  S3/GCS  │
│  Cache   │              │  Storage │
└──────────┘              └──────────┘

External APIs:
┌──────────┐  ┌──────────┐  ┌──────────┐
│  Azure   │  │  Slack   │  │  GitHub  │
│ DevOps   │  │   API    │  │   API    │
└──────────┘  └──────────┘  └──────────┘
```

---

## 📦 Modelo de Datos Multi-tenant

### Schema PostgreSQL

```sql
-- Organizaciones (tenants)
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    plan VARCHAR(50) NOT NULL, -- free, starter, pro, enterprise
    status VARCHAR(50) DEFAULT 'active', -- active, suspended, cancelled
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Usuarios
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    avatar_url TEXT,
    auth_provider VARCHAR(50), -- azure, github, google
    auth_provider_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    last_login_at TIMESTAMP
);

-- Membresías (users <-> orgs)
CREATE TABLE memberships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL, -- owner, admin, developer, viewer
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, organization_id)
);

-- Proyectos (repos)
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    provider VARCHAR(50) NOT NULL, -- azure_devops, github, gitlab
    provider_org VARCHAR(255) NOT NULL,
    provider_project VARCHAR(255) NOT NULL,
    provider_repo VARCHAR(255) NOT NULL,
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Reglas de auto-aprobación
CREATE TABLE approval_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    enabled BOOLEAN DEFAULT true,
    priority INT DEFAULT 0,
    conditions JSONB NOT NULL, -- {branch: "develop", no_conflicts: true, ...}
    actions JSONB NOT NULL, -- {auto_approve: true, notify_slack: true, ...}
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Pull Requests (cache + histórico)
CREATE TABLE pull_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    provider_pr_id VARCHAR(100) NOT NULL,
    title TEXT,
    author VARCHAR(255),
    source_branch VARCHAR(255),
    target_branch VARCHAR(255),
    status VARCHAR(50), -- active, completed, abandoned
    verdict VARCHAR(100),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    UNIQUE(project_id, provider_pr_id)
);

-- Eventos (audit log)
CREATE TABLE events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    pr_id UUID REFERENCES pull_requests(id) ON DELETE SET NULL,
    event_type VARCHAR(100) NOT NULL, -- pr.approved, pr.rejected, rule.created, ...
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Métricas agregadas (para analytics)
CREATE TABLE metrics_daily (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    prs_opened INT DEFAULT 0,
    prs_merged INT DEFAULT 0,
    prs_rejected INT DEFAULT 0,
    avg_review_time_minutes INT,
    avg_merge_time_minutes INT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(project_id, date)
);

-- Integraciones
CREATE TABLE integrations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    type VARCHAR(50) NOT NULL, -- slack, sheets, jira, teams
    config JSONB NOT NULL, -- encrypted credentials
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Índices para performance
CREATE INDEX idx_prs_project_status ON pull_requests(project_id, status);
CREATE INDEX idx_prs_updated ON pull_requests(updated_at DESC);
CREATE INDEX idx_events_org_created ON events(organization_id, created_at DESC);
CREATE INDEX idx_metrics_project_date ON metrics_daily(project_id, date DESC);
CREATE INDEX idx_memberships_user ON memberships(user_id);
CREATE INDEX idx_memberships_org ON memberships(organization_id);
```

---

## 🔐 Autenticación y Autorización

### OAuth Flow (Azure DevOps)

```python
# auth/oauth.py
from fastapi import APIRouter, HTTPException
from authlib.integrations.starlette_client import OAuth

router = APIRouter()
oauth = OAuth()

oauth.register(
    name='azure',
    client_id=settings.AZURE_CLIENT_ID,
    client_secret=settings.AZURE_CLIENT_SECRET,
    authorize_url='https://app.vssps.visualstudio.com/oauth2/authorize',
    access_token_url='https://app.vssps.visualstudio.com/oauth2/token',
    client_kwargs={'scope': 'vso.code vso.project'}
)

@router.get('/login/azure')
async def login_azure(request: Request):
    redirect_uri = request.url_for('auth_callback_azure')
    return await oauth.azure.authorize_redirect(request, redirect_uri)

@router.get('/callback/azure')
async def auth_callback_azure(request: Request):
    token = await oauth.azure.authorize_access_token(request)
    user_info = await oauth.azure.get('https://app.vssps.visualstudio.com/_apis/profile/profiles/me')
    
    # Crear o actualizar usuario
    user = await get_or_create_user(
        email=user_info['emailAddress'],
        name=user_info['displayName'],
        auth_provider='azure',
        auth_provider_id=user_info['id']
    )
    
    # Generar JWT
    access_token = create_access_token(user.id)
    return {'access_token': access_token, 'token_type': 'bearer'}
```

### Middleware de Tenant Isolation

```python
# middleware/tenant.py
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Extraer org_id del token JWT o subdomain
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            raise HTTPException(401, "No autorizado")
        
        payload = decode_jwt(token)
        user_id = payload.get('user_id')
        
        # Obtener org_id del path o header
        org_slug = request.path_params.get('org_slug')
        if org_slug:
            org = await get_org_by_slug(org_slug)
            # Verificar que el usuario pertenece a la org
            membership = await get_membership(user_id, org.id)
            if not membership:
                raise HTTPException(403, "Acceso denegado")
            
            # Inyectar contexto de tenant
            request.state.organization_id = org.id
            request.state.user_id = user_id
            request.state.user_role = membership.role
        
        response = await call_next(request)
        return response
```

### RBAC (Role-Based Access Control)

```python
# auth/permissions.py
from enum import Enum
from functools import wraps

class Role(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    DEVELOPER = "developer"
    VIEWER = "viewer"

class Permission(str, Enum):
    # Projects
    PROJECT_CREATE = "project:create"
    PROJECT_READ = "project:read"
    PROJECT_UPDATE = "project:update"
    PROJECT_DELETE = "project:delete"
    
    # Rules
    RULE_CREATE = "rule:create"
    RULE_UPDATE = "rule:update"
    RULE_DELETE = "rule:delete"
    
    # PRs
    PR_APPROVE = "pr:approve"
    PR_REJECT = "pr:reject"
    PR_COMPLETE = "pr:complete"

ROLE_PERMISSIONS = {
    Role.OWNER: [p for p in Permission],  # all
    Role.ADMIN: [
        Permission.PROJECT_CREATE, Permission.PROJECT_READ, Permission.PROJECT_UPDATE,
        Permission.RULE_CREATE, Permission.RULE_UPDATE, Permission.RULE_DELETE,
        Permission.PR_APPROVE, Permission.PR_REJECT, Permission.PR_COMPLETE,
    ],
    Role.DEVELOPER: [
        Permission.PROJECT_READ,
        Permission.PR_APPROVE, Permission.PR_REJECT,
    ],
    Role.VIEWER: [
        Permission.PROJECT_READ,
    ],
}

def require_permission(permission: Permission):
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            role = request.state.user_role
            if permission not in ROLE_PERMISSIONS.get(role, []):
                raise HTTPException(403, "Permiso denegado")
            return await func(request, *args, **kwargs)
        return wrapper
    return decorator
```

---

## ⚡ Sistema de Colas (Celery)

### Configuración

```python
# workers/celery_app.py
from celery import Celery

celery_app = Celery(
    'pr_dashboard',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/1'
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 min timeout
    task_soft_time_limit=240,
)
```

### Tasks

```python
# workers/tasks.py
from workers.celery_app import celery_app
from core.pr_processor import process_pr

@celery_app.task(bind=True, max_retries=3)
def process_pr_async(self, pr_id: str, project_id: str):
    """Procesa un PR en background."""
    try:
        result = process_pr(pr_id, project_id)
        return result
    except Exception as exc:
        # Retry con exponential backoff
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)

@celery_app.task
def sync_prs_for_project(project_id: str):
    """Sincroniza todos los PRs activos de un proyecto."""
    prs = fetch_active_prs(project_id)
    for pr in prs:
        process_pr_async.delay(pr['id'], project_id)

@celery_app.task
def aggregate_daily_metrics(date: str):
    """Agrega métricas diarias para todas las orgs."""
    orgs = get_all_organizations()
    for org in orgs:
        calculate_metrics(org.id, date)

# Scheduled tasks
celery_app.conf.beat_schedule = {
    'sync-prs-every-5min': {
        'task': 'workers.tasks.sync_all_projects',
        'schedule': 300.0,  # 5 minutes
    },
    'aggregate-metrics-daily': {
        'task': 'workers.tasks.aggregate_daily_metrics',
        'schedule': crontab(hour=0, minute=0),  # midnight
    },
}
```

---

## 🔄 Webhooks (Event-Driven)

### Recibir Webhooks de Azure DevOps

```python
# api/webhooks.py
from fastapi import APIRouter, Request, HTTPException
from workers.tasks import process_pr_async

router = APIRouter()

@router.post('/webhooks/azure/{project_id}')
async def azure_webhook(project_id: str, request: Request):
    """Recibe eventos de Azure DevOps."""
    # Verificar signature
    signature = request.headers.get('X-Azure-Signature')
    body = await request.body()
    if not verify_azure_signature(signature, body):
        raise HTTPException(401, "Signature inválida")
    
    payload = await request.json()
    event_type = payload.get('eventType')
    
    if event_type == 'git.pullrequest.created':
        pr_id = payload['resource']['pullRequestId']
        # Procesar en background
        process_pr_async.delay(str(pr_id), project_id)
    
    elif event_type == 'git.pullrequest.updated':
        pr_id = payload['resource']['pullRequestId']
        process_pr_async.delay(str(pr_id), project_id)
    
    elif event_type == 'git.pullrequest.merged':
        pr_id = payload['resource']['pullRequestId']
        # Actualizar métricas
        update_pr_metrics.delay(str(pr_id), project_id)
    
    return {'status': 'received'}
```

---

## 📊 Caching Strategy

```python
# cache/redis_client.py
import redis
import json
from typing import Optional, Any

redis_client = redis.Redis(
    host='localhost',
    port=6379,
    db=0,
    decode_responses=True
)

class Cache:
    @staticmethod
    def get(key: str) -> Optional[Any]:
        value = redis_client.get(key)
        return json.loads(value) if value else None
    
    @staticmethod
    def set(key: str, value: Any, ttl: int = 300):
        redis_client.setex(key, ttl, json.dumps(value))
    
    @staticmethod
    def delete(key: str):
        redis_client.delete(key)
    
    @staticmethod
    def invalidate_pattern(pattern: str):
        keys = redis_client.keys(pattern)
        if keys:
            redis_client.delete(*keys)

# Uso
def get_project_prs(project_id: str):
    cache_key = f"project:{project_id}:prs"
    cached = Cache.get(cache_key)
    if cached:
        return cached
    
    prs = fetch_prs_from_db(project_id)
    Cache.set(cache_key, prs, ttl=60)  # 1 min
    return prs

# Invalidar cache cuando hay cambios
def on_pr_updated(project_id: str):
    Cache.invalidate_pattern(f"project:{project_id}:*")
```

---

## 🚀 Deployment (Kubernetes)

### Dockerfile

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Dependencias del sistema
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código
COPY . .

# Usuario no-root
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Kubernetes Manifests

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: pr-dashboard-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: pr-dashboard-api
  template:
    metadata:
      labels:
        app: pr-dashboard-api
    spec:
      containers:
      - name: api
        image: pr-dashboard:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: url
        - name: REDIS_URL
          value: redis://redis-service:6379
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: pr-dashboard-api
spec:
  selector:
    app: pr-dashboard-api
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: pr-dashboard-api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: pr-dashboard-api
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

---

## 📈 Monitoreo y Observabilidad

### Prometheus Metrics

```python
# monitoring/metrics.py
from prometheus_client import Counter, Histogram, Gauge

# Contadores
pr_processed_total = Counter(
    'pr_processed_total',
    'Total PRs procesados',
    ['organization', 'project', 'verdict']
)

api_requests_total = Counter(
    'api_requests_total',
    'Total requests HTTP',
    ['method', 'endpoint', 'status']
)

# Histogramas (latencia)
pr_processing_duration = Histogram(
    'pr_processing_duration_seconds',
    'Tiempo de procesamiento de PR',
    ['organization', 'project']
)

api_request_duration = Histogram(
    'api_request_duration_seconds',
    'Latencia de requests HTTP',
    ['method', 'endpoint']
)

# Gauges (estado actual)
active_prs = Gauge(
    'active_prs',
    'PRs activos por proyecto',
    ['organization', 'project']
)

# Uso
@pr_processing_duration.time()
def process_pr(pr_id, project_id):
    # ... lógica ...
    pr_processed_total.labels(
        organization=org_id,
        project=project_id,
        verdict=verdict
    ).inc()
```

### Structured Logging

```python
# logging_config.py
import structlog

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Uso
logger.info(
    "pr_processed",
    pr_id=pr_id,
    project_id=project_id,
    verdict=verdict,
    duration_ms=duration
)
```

---

## 🔒 Seguridad

### Secrets Management

```python
# config/secrets.py
from google.cloud import secretmanager

client = secretmanager.SecretManagerServiceClient()

def get_secret(secret_id: str) -> str:
    name = f"projects/{PROJECT_ID}/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")

# Uso
DATABASE_URL = get_secret("database-url")
AZURE_CLIENT_SECRET = get_secret("azure-client-secret")
```

### Rate Limiting

```python
# middleware/rate_limit.py
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

# Por IP
@app.get("/api/prs")
@limiter.limit("100/minute")
async def get_prs(request: Request):
    pass

# Por tenant
@limiter.limit("1000/hour", key_func=lambda: request.state.organization_id)
async def process_webhook(request: Request):
    pass
```

---

## 💾 Backup y Disaster Recovery

```bash
# scripts/backup.sh
#!/bin/bash

# Backup PostgreSQL
pg_dump $DATABASE_URL | gzip > backup-$(date +%Y%m%d-%H%M%S).sql.gz

# Upload a S3
aws s3 cp backup-*.sql.gz s3://pr-dashboard-backups/

# Retener últimos 30 días
find . -name "backup-*.sql.gz" -mtime +30 -delete

# Cron: diario a las 2am
# 0 2 * * * /app/scripts/backup.sh
```

---

## 📚 Próximos Pasos de Implementación

1. **Setup inicial** (Semana 1)
   - Crear repo con estructura FastAPI
   - Setup PostgreSQL + Redis local
   - Implementar modelos SQLAlchemy

2. **Auth + Multi-tenancy** (Semana 2-3)
   - OAuth con Azure DevOps
   - Middleware de tenant isolation
   - RBAC básico

3. **Migrar lógica core** (Semana 4-5)
   - Adaptar check_salesforce_prs.py
   - Implementar workers Celery
   - Tests unitarios

4. **Frontend** (Semana 6-7)
   - React app con TypeScript
   - Dashboard multi-proyecto
   - Configuración de reglas

5. **Deploy** (Semana 8)
   - Docker + Kubernetes
   - CI/CD con GitHub Actions
   - Monitoreo con Prometheus

¿Quieres que profundice en alguna parte específica?
