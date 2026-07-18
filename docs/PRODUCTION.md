# Production Deployment Guide

The repository includes production safeguards, but production readiness also
depends on managed infrastructure, secret handling, monitoring, and operational
procedures outside the codebase.

## Runtime architecture

Deploy these as separate processes or managed services:

1. FastAPI web service built from `docker/Dockerfile`.
2. Celery worker built from the same image.
3. Redis-compatible durable Celery broker.
4. Postgres with backups and point-in-time recovery.
5. Qdrant with persistent storage and backups.
6. Supabase Storage or an equivalent configured Supabase project.
7. React/Cloudflare frontend from `frontend/`.

Do not run production ingestion with FastAPI `BackgroundTasks`. Set
`TASK_QUEUE_MODE=celery`; production configuration validation enforces this.

## Required production configuration

Start from `backend/.env.example`, inject values through the deployment platform,
and do not copy a `.env` file into the container.

At minimum, production must set:

```env
ENVIRONMENT=production
AUTO_CREATE_TABLES=false
ALLOW_INSECURE_EMAIL_AUTH=false
ENABLE_API_DOCS=false
FORCE_HTTPS=false

DATABASE_HOST=managed-postgres-host
DB_USERNAME=application-user
DB_PASSWORD=strong-database-secret
DB_NAME=application-database
DB_SSLMODE=require

SECRET_KEY=a-random-secret-containing-at-least-32-characters
BACKEND_CORS_ORIGINS=https://app.example.com
TRUSTED_HOSTS=api.example.com

TASK_QUEUE_MODE=celery
CELERY_BROKER_URL=rediss://managed-redis-host/0
CELERY_RESULT_BACKEND=rediss://managed-redis-host/1

SUPABASE_URL=https://project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=secret
SUPABASE_STORAGE_BUCKET=images

QDRANT_URL=https://managed-qdrant-host
QDRANT_API_KEY=secret
```

Terminate TLS at the platform load balancer. Set `FORCE_HTTPS=true` only when
proxy forwarding headers are correctly trusted; otherwise redirect loops are
possible. Restrict the container port so only the load balancer can reach it.

## Build and release

Build from the repository root:

```powershell
docker build --file docker/Dockerfile --tag ai-image-classifier-api .
```

Run migrations once as a release job before rolling out web or worker replicas:

```powershell
alembic -c backend/alembic.ini upgrade head
```

Do not run migrations independently in every web replica. A single release job
avoids migration races and gives the deployment system a clear failure point.

Run the web process:

```text
uvicorn main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips=<trusted-proxy-cidr>
```

Run one or more worker processes:

```text
celery --app src.tasks:celery_app worker --loglevel INFO --concurrency 1
```

Start with worker concurrency 1 because InsightFace is memory-heavy. Increase it
only after measuring container memory and model initialization behavior.

## Health checks

- `GET /health/live`: process liveness; does not contact dependencies.
- `GET /health/ready`: readiness; returns HTTP 503 if Postgres is unavailable.
- `GET /health`: backward-compatible database readiness endpoint.

Use liveness for restart decisions and readiness for load-balancer traffic.

## Security checklist

- Keep `ALLOW_INSECURE_EMAIL_AUTH=false`; production login should use verified
  Google identity.
- Generate `SECRET_KEY` with a cryptographically secure random generator and
  rotate it through a planned session invalidation.
- Store Google refresh tokens and service keys in a managed secret store. The
  current database columns are not application-encrypted, so enable database
  encryption at rest and add envelope encryption for stronger token protection.
- Put rate limits on `/auth/*`, `/search`, and ingestion-start routes at the API
  gateway or reverse proxy.
- Restrict CORS and trusted hosts to exact production domains.
- Give Postgres, Qdrant, Redis, and Supabase credentials the least privileges
  supported by each service.
- Scan the image and Python dependencies in CI before release.

## InsightFace model operations

InsightFace may download `buffalo_l` on first initialization. Production workers
should not depend on unrestricted runtime internet access. Pre-populate the
worker image or mount a read-only model cache at the InsightFace home directory,
and verify the model artifact checksum in the build pipeline.

Run one warm-up inference before marking a worker ready if cold-start latency is
unacceptable.

## Observability

Request logs include method, path, status, duration, and `X-Request-ID`. Preserve
that header through the load balancer and include it in frontend error reports.

At minimum, alert on:

- readiness failures and HTTP 5xx rate;
- request latency percentiles;
- Celery queue depth and oldest-message age;
- jobs stuck in queued or running states;
- ingestion failure rate;
- Postgres pool exhaustion;
- Qdrant/Supabase/Drive error rates;
- worker memory and restart count.

Centralize logs outside the container. Container-local rotating files are not a
durable log store.

## Backups and recovery

- Enable automated Postgres backups and test point-in-time restoration.
- Snapshot or back up Qdrant collections.
- Define Supabase object retention and recovery policies.
- Redis is a queue, not the application source of truth, but configure broker
  durability so accepted jobs survive ordinary restarts.
- Periodically reconcile Postgres Face rows, Qdrant points, and Supabase objects.

## Remaining application-level work

Before handling sensitive real-world identity data at scale, add:

- application-level encryption for stored Google tokens;
- refresh-token rotation/revocation records;
- explicit user consent, retention, and account-deletion workflows;
- reconciliation and cleanup jobs across Postgres, Qdrant, and Supabase;
- integration tests against disposable real service instances;
- a privacy/security review appropriate for biometric data and local law.
