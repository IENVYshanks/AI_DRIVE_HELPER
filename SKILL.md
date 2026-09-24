---
name: ai-image-classifier-engineering
description: "Use when changing this AI Image Classifier: work on one explicitly named behavior at a time, require a change proposal and explicit user approval before edits, preserve FastAPI/React module boundaries and development/production parity, add focused tests, and verify compatibility across Postgres, Supabase, Qdrant, Google Drive, InsightFace, and Celery integrations."
---

# AI Image Classifier Engineering

Use this skill for every implementation, bug fix, refactor, migration, API change, ingestion/search pipeline change, dependency update, and deployment change in this project.

## Required platform and toolchain

- Use Python 3.12 for the backend and production image. Keep backend code compatible with the pinned `python:3.12-slim` base unless an approved requirement changes the runtime.
- Use FastAPI for HTTP APIs, Pydantic Settings for validated configuration, SQLAlchemy for Postgres persistence, and Alembic for versioned schema migrations.
- Use Celery with Redis for durable production ingestion jobs. The FastAPI `BackgroundTasks` path is a development convenience selected by `TASK_QUEUE_MODE=background`; production uses `TASK_QUEUE_MODE=celery`.
- Use InsightFace with ONNX Runtime for face detection and embeddings, Qdrant for similarity vectors, Supabase Storage for image objects, Google Drive APIs for source files, and Postgres for application state.
- Use React 19 and strict TypeScript for the primary frontend, with TanStack Start/Router, Vite, Tailwind CSS, and the existing component system. Do not replace these frameworks without an approved requirement.
- Use npm for JavaScript dependencies. The root `package-lock.json` owns the combined development launcher; `frontend/package-lock.json` owns the frontend application. Do not introduce Yarn, pnpm, or additional lockfile formats. The legacy `bun.lockb` is not authority for new dependency changes.
- Use Python `unittest` for the existing backend suite and the frontend's existing TypeScript, ESLint, Prettier, and Vite checks. Add a new test framework only when an approved requirement justifies it.
- Preserve request IDs, bounded logs, liveness/readiness endpoints, security headers, and safe production configuration. Extend observability through project-owned logging and metrics boundaries rather than provider-specific calls scattered through domain code.

## Non-negotiable workflow

### 0. Work on one task at a time

- Treat each user-approved task as one explicitly named behavior or capability, such as Google session exchange, folder registration, ingestion retry, progress polling, library listing, uploaded-image search, or deployment health checks.
- Do not combine adjacent features merely because they share a router, page, model, or provider. A search task must not also redesign ingestion or authentication unless the user explicitly expands and approves the scope.
- Limit inspection, proposals, implementation, documentation, migrations, and tests to the selected behavior and the minimum shared dependencies required to implement it safely.
- If the selected behavior requires a shared API type, model, migration, environment key, provider adapter, or frontend state change, include only the smallest necessary change and identify it explicitly in the proposal.
- Report unrelated defects, refactors, security improvements, and follow-up opportunities separately without implementing them. Obtain explicit approval before treating one as a new task.
- Completing one task does not authorize starting the next task. Stop after the completion report and wait for the user to select or approve another task.
- Run focused validation first. Broader regression checks do not authorize unrelated fixes.

### 1. Inspect before proposing

Before changing any file:

- Read the relevant router or route, service, ingestion stage, model, migration, configuration, tests, and nearby callers.
- Identify the owning layer, its public API or UI contract, its persisted state, external providers, and downstream consumers.
- Trace frontend API calls through `frontend/src/lib/api.ts` when the behavior crosses the HTTP boundary.
- For ingestion or search changes, identify transaction boundaries, retry behavior, user filters, object/vector identifiers, and failure-state transitions.
- Check the current commands and run the narrowest relevant existing test when practical.
- Do not edit files while gathering this context.

### 2. Propose and obtain approval

Before the first edit, show the user a concise change proposal and wait for explicit approval. The proposal must include:

- The behavior or defect being addressed.
- The exact files and backend/frontend layers expected to change.
- The intended implementation and why it preserves module and provider boundaries.
- API, frontend contract, database, migration, environment, queue, storage, vector-index, and compatibility impacts.
- Tests to add or update for each changed endpoint, state transition, or pipeline stage.
- Validation commands and broader regression checks to run afterward.
- Assumptions, external-service requirements, rollout risks, and any data migration or re-ingestion implications.

Do not infer approval from the original implementation request alone. If the user has not approved the proposal, ask for approval instead of editing.

### 3. Implement in small, reversible slices

- Keep each edit focused on the approved behavior and its explicitly approved supporting changes.
- Preserve existing behavior unless the proposal says it changes.
- Do not modify unrelated files or hide formatting churn in functional changes.
- After the first substantive edit, run the narrowest relevant test, syntax check, type check, lint check, or contract check before expanding the change.
- Repair failures in the same slice and rerun the focused check before continuing.
- Never use real user images, live OAuth tokens, service-role credentials, or production databases to validate ordinary code changes.

## Architecture rules

- Keep the backend as a modular monolith. HTTP concerns belong in `backend/src/routers/`, reusable business and provider operations in `backend/src/services/`, pipeline orchestration in `backend/src/ingestion/`, persistence records in `backend/src/models/`, and application assembly in `backend/src/app.py`.
- Routers validate HTTP input, resolve the authenticated user, enforce ownership, and shape responses. Routers must not implement provider workflows or duplicate persistence rules.
- Services own focused domain or provider behavior. Wrap Google Drive, Supabase, Qdrant, InsightFace, and authentication libraries behind project-owned service functions so SDK shapes do not leak across the application.
- The ingestion job runner owns folder/job lifecycle. The file processor owns the transaction and observable result for one image. State helpers must remain usable with `auto_commit=False` when a caller needs an atomic multi-record transition.
- Background work must create and close its own SQLAlchemy session. Never pass a request-scoped session into FastAPI background work or Celery tasks.
- Keep development background execution and Celery execution behaviorally equivalent. Both paths call the same ingestion service entry point with identifiers, not ORM objects, tokens, or image bytes.
- Keep protected operations scoped by authenticated `user_id` across Postgres queries and Qdrant filters. A record owned by another user must not be returned merely because its UUID is known.
- Access tokens may authorize protected operations; refresh tokens may not. Google Drive tokens remain backend-only, use versioned authenticated encryption at rest, and must never be logged, returned unnecessarily, or placed in queue payloads.
- Store durable identity and metadata in Postgres. Store image bytes in Supabase and face vectors in Qdrant. Signed object URLs are temporary response values and must not become canonical persisted identifiers.
- Keep Qdrant vector payloads sufficient for user filtering and Postgres reconciliation. Coordinate vector writes and deletes with persisted face/image state so partial failures remain detectable and retryable.
- Keep retries bounded and idempotent. Existing ingestion intentionally performs one retry pass for failed files; any change to attempts, backoff, duplicate handling, or terminal state requires explicit approval and tests.
- Do not create a network service merely to enforce a source-code boundary. Extract a service only when measured scaling, reliability, security, or ownership needs justify it.
- The React frontend communicates with backend capabilities through `frontend/src/lib/api.ts`; it must not connect directly to Postgres, Supabase service APIs, Qdrant, or Google Drive using privileged credentials.
- Use file-based routes under `frontend/src/routes/`. Do not hand-edit generated `frontend/src/routeTree.gen.ts`.
- `@lovable.dev/vite-tanstack-config` already provides the TanStack, React, Tailwind, Cloudflare, path-alias, environment, and development plugins. Do not duplicate them in `frontend/vite.config.ts`.
- Guard `window`, `localStorage`, `File`, and other browser-only APIs in code that can execute during server rendering.
- Treat `backend/frontend.py` as a legacy companion UI. Change it only when the approved task explicitly includes Streamlit behavior or compatibility.

## Development-to-production parity

- Build the backend from `docker/Dockerfile` and promote the same immutable image between environments. Use different commands for FastAPI and Celery roles rather than rebuilding application code per role.
- Keep application behavior environment-neutral. Express development, test, and production differences through validated settings and injected provider configuration, not scattered environment checks.
- Load backend settings from process environment or `backend/.env`. Keep `backend/.env.example` synchronized when a key is added, removed, renamed, or changes meaning.
- Expose only safe `VITE_*` values to the frontend. Keep `frontend/.env.example` synchronized and never place service-role, database, Qdrant, JWT, or OAuth-client secrets in frontend configuration.
- Production must keep `AUTO_CREATE_TABLES=false`, `TASK_QUEUE_MODE=celery`, secure session cookies, explicit trusted hosts/CORS origins, complete Supabase and Google OAuth settings, configured OAuth token-encryption keys, and a configured Celery broker.
- Apply Alembic migrations as a dedicated deployment step before starting code that depends on them. Do not run migrations automatically in every API or worker replica.
- Keep migrations compatible with the currently deployed and immediately previous application version where rolling deployment is expected. Use expand/migrate/contract sequencing for destructive schema changes.
- Keep `backend/schema.sql` synchronized as the documented full-schema reference, but treat Alembic revisions as deployment authority.
- Use real protocol-compatible dependencies for integration tests: Postgres, Redis/Celery, Qdrant, and S3/Supabase-compatible object storage where relevant. Unit tests use fakes or mocks at project-owned provider boundaries.
- Keep liveness independent of external services and readiness dependent on required serving dependencies. Do not make `/health/live` fail because Postgres, Qdrant, Supabase, Google, or Redis is temporarily unavailable.
- Preserve image-size limits, connection timeouts, bounded retries, bounded logging, non-root container execution, and graceful disposal of database sessions and engines.
- Secrets must come from environment injection or a secret manager. Never commit `.env`, `.env.local`, Streamlit secrets, credentials, access/refresh tokens, downloaded user images, model weights, or production logs.

## Python, TypeScript, and dependency rules

- Keep backend request and response contracts explicit with Pydantic models. Do not return raw SQLAlchemy records when the response requires derived or security-sensitive fields.
- Use typed Python interfaces and focused functions. Avoid untyped dictionaries across module boundaries when a Pydantic model, dataclass, protocol, or existing model provides a stable contract.
- Do not expose raw provider SDK exceptions or response objects as API contracts. Translate them into stable service results and safe HTTP errors at the owning boundary.
- Avoid blocking provider, model, or database work directly on the async event loop. Follow the existing `run_in_threadpool` pattern for synchronous operations called by async routes.
- Make provider operations use explicit timeouts where supported. Classify retryable and terminal failures at provider boundaries; do not infer domain state from arbitrary SDK message strings.
- Queue payloads contain identifiers and immutable operation metadata, not ORM instances, OAuth tokens, image bytes, signed URLs, or complete database records.
- Keep TypeScript `strict` enabled. Narrow `unknown` explicitly and do not use `any` to bypass frontend/backend contract mismatches.
- Centralize frontend transport and response types in `frontend/src/lib/api.ts` or a deliberately introduced contract module. When a backend response changes, update all TypeScript consumers in the same approved change.
- Preserve accessible semantics, keyboard behavior, loading states, empty states, and actionable errors when changing user-facing flows.
- Add Python dependencies only to `backend/requirements.txt` with bounds compatible with the existing style. Add root launcher dependencies to the root package and frontend dependencies to `frontend/package.json`; update the corresponding lockfile only.
- Review new dependencies for maintenance, license, install size, native/runtime requirements, and security impact. InsightFace/ONNX and image-processing changes must account for container libraries, model download/cache behavior, CPU/memory use, and cold starts.

## API and pipeline testing requirements

Every changed API endpoint must have tests covering, as applicable:

- Valid input and the expected status and response contract.
- Authentication, access-token enforcement, ownership/user isolation, and validation failures.
- Stable errors for missing records, provider failure, queue failure, oversized images, unsupported media, and absent faces.
- Idempotency or duplicate behavior for registration, folder upsert, job start, ingestion, and search persistence.
- Compatibility between backend response models and `frontend/src/lib/api.ts` types.

Every changed ingestion, search, background-task, or provider flow must have tests covering, as applicable:

- The happy path from input to persisted and returned result.
- State transitions for folders, jobs, images, faces, queries, and results.
- Transaction ownership, rollback, partial failure, bounded retry, duplicate delivery, and terminal failure behavior.
- Development background execution and Celery worker execution using the same service entry point.
- Postgres metadata, Supabase object keys, Qdrant vector IDs/payloads, and cleanup or reconciliation after partial failure.
- Provider and model failures using mocks, fakes, or fixtures rather than live services in unit tests.
- User-scoped Qdrant searches and Postgres resolution so cross-user results cannot leak.

Use unit tests for state and domain logic, API tests for FastAPI behavior, integration tests for real persistence/queue/vector/storage boundaries, and a small number of end-to-end tests for critical sign-in, ingestion, progress, library, and search journeys. New behavior is incomplete until the relevant tests are present and passing.

## Database and migration requirements

When changing persisted data:

1. Update the owning SQLAlchemy model and all relationships, queries, serializers, fixtures, and state helpers.
2. Add an Alembic revision under `backend/alembic/versions/`; do not rely on `Base.metadata.create_all` as the production migration.
3. Update `backend/schema.sql` when it represents the changed schema.
4. Define upgrade, compatibility, backfill, re-ingestion, vector-rebuild, and downgrade expectations in the proposal.
5. Test the migration against representative existing data when the change transforms or constrains stored values.

Do not silently rewrite or delete user image metadata, stored objects, face vectors, search history, or ingestion history. Destructive cleanup or re-indexing requires explicit approval, exact scope, and a recovery or reconciliation plan.

## Change propagation and regression safety

When changing an endpoint, frontend type, database column, environment key, queue task, storage key, vector payload, embedding assumption, shared interface, or domain rule:

1. Find all definitions, references, producers, consumers, serializers, models, migrations, fixtures, tests, documentation, and deployment configuration.
2. Update every affected backend and frontend consumer in the same change, or document an approved staged compatibility plan.
3. Run the narrowest affected tests first, then backend syntax/tests and frontend type/lint/build checks as relevant.
4. Verify migrations, production configuration, Celery/background parity, user scoping, and provider failure handling for the changed behavior.
5. Review the final diff for secrets, missing ownership filters, leaked provider types, blocking async work, inconsistent state transitions, generated-file edits, unrelated changes, and stale documentation.

Do not declare work complete while a known regression remains. Report unavailable or environment-blocked checks precisely, including the reason and the safest next validation.

## Project commands

Install from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
npm install
npm --prefix frontend install
```

Run both development servers:

```powershell
npm run dev
```

Run only one side with `npm run dev:backend` or `npm run dev:frontend`.

Run backend checks from the repository root:

```powershell
.\.venv\Scripts\python.exe -m compileall -q backend
Set-Location backend
..\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Run frontend checks from the repository root:

```powershell
npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend run build
npm --prefix frontend run format:check
```

`npm --prefix frontend run check` runs type checking, linting, and the production build together. Use focused commands during implementation and the combined check before completion when the frontend changed.

## Completion report

After implementation, report:

- What changed and which backend/frontend layer owns it.
- Endpoints, frontend contracts, models, migrations, queue tasks, storage keys, vector payloads, embedding behavior, and environment configuration affected.
- Tests added or updated.
- Validation commands and their results.
- Compatibility, rollout, migration, backfill, re-ingestion, re-indexing, or provider risks.
- Checks not run or blocked by unavailable services, secrets, model assets, or network access.

Unless the approved task defines stricter checks, run backend compile/tests for backend changes and `npm --prefix frontend run check` plus `npm --prefix frontend run format:check` for frontend changes. Run integration or end-to-end suites when the change crosses those boundaries and the required services are available.
