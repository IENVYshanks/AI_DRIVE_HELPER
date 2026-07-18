# AI Image Classifier — Interview Explanation Guide

This guide is written to help you explain the project aloud. Start with the short
version, then go deeper only when the interviewer asks.

## 1. The 30-second explanation

> This is a full-stack face-search application. A user signs in with Google and
> selects a Google Drive folder. The backend downloads the folder's images,
> detects faces with InsightFace, stores image metadata in Postgres, stores the
> image files in Supabase, and stores face embeddings in Qdrant. Later, the user
> uploads a query photo. The backend creates an embedding for its main face,
> searches Qdrant for similar vectors, resolves the matching face IDs back to
> Postgres images, and returns temporary Supabase URLs to the React frontend.

That explanation establishes the problem, input, processing, storage, and output.

## 2. The problem the project solves

A normal file store can search by filename or metadata, but it cannot answer:
“Which of my photos contain a person who looks like this query photo?”

The project solves that by converting every detected face into an embedding: a
list of numbers rep resenting facial features. Similar faces produce vectors that
are close to each other, so a vector database can retrieve likely matches.

The application is user-scoped. A user's query only searches embeddings belonging
to that user.

## 3. High-level architecture

```text
                         AI Image Classifier

 React frontend
      |
      | HTTP + JWT
      v
 FastAPI routers
      |
      v
 Business services and ingestion coordinator
      |
      +-------- Google Drive: original image source
      +-------- InsightFace: face detection and embeddings
      +-------- Postgres: users, jobs, images, faces, search history
      +-------- Supabase Storage: copied image bytes
      `-------- Qdrant: searchable face vectors
```

Each storage system has a different purpose:

| System | Stores | Why it is used |
|---|---|---|
| Postgres | Users, folders, jobs, images, faces, search history | Relational data, ownership, progress, and durable application state |
| Qdrant | Face embeddings and identifier payloads | Efficient nearest-neighbor vector search |
| Supabase Storage | Image bytes | Object storage and temporary signed image URLs |
| Google Drive | User's source photos | External source selected by the user |

An important design idea is that Postgres is the application source of truth,
while Qdrant is a specialized search index. The same face ID connects the two.

## 4. Repository structure

```text
backend/
  main.py                    ASGI entrypoint used by Uvicorn
  frontend.py                older Streamlit companion interface
  schema.sql                 reference Postgres schema
  src/
    app.py                   creates and configures FastAPI
    dependencies.py          resolves the authenticated user
    db/                      settings, engine, and database sessions
    models/                  SQLAlchemy table mappings
    routers/                 HTTP request and response layer
    services/                business logic and external integrations
    ingestion/               folder and per-file workflow coordination

frontend/
  src/
    routes/                  page-level React components
    components/              shared page and UI components
    hooks/                   reusable React state behavior
    lib/api.ts               typed backend HTTP client
    lib/auth.ts              Google and backend login flow
    lib/photo-store.ts       small browser-side photo store
```

## 5. Backend request layers

### `backend/main.py`

This is deliberately small. Uvicorn imports `main:app`, and `main.py` calls
`create_app()` from `src/app.py`.

How to explain it:

> The entrypoint contains no business logic. It only exposes the configured ASGI
> application, which makes startup easy to locate and application construction
> reusable in tests or alternate deployment environments.

### `backend/src/app.py`

`create_app()`:

1. Loads settings.
2. Configures rotating file and console logging.
3. Optionally creates database tables in development.
4. Creates the FastAPI application.
5. Adds CORS middleware.
6. Registers authentication, ingestion, and search routers.
7. Adds the database-aware `/health` endpoint.

CORS is required because the React development server and backend run on
different origins.

### `backend/src/dependencies.py`

`get_current_user()` is injected into protected routes with FastAPI `Depends`.
It extracts the bearer token, verifies the JWT, requires an access token rather
than a refresh token, parses the subject as a user UUID, and loads the User row.

Why this is useful:

> Authentication is implemented once. Every protected route receives a trusted
> User object and can scope database operations using that user's ID.

## 6. Configuration and database components

### `backend/src/config_env.py`

This small loader reads `backend/.env` and places missing values into the process
environment. Existing environment variables win, which is important in deployed
environments where secrets are injected externally.

### `backend/src/db/config.py`

`Settings` uses Pydantic Settings to validate environment variables. It also:

- constructs an escaped Postgres URL;
- converts comma-separated CORS origins into a list;
- prevents automatic table creation in production.

`get_settings()` is cached so integrations use one consistent configuration
snapshot and do not repeatedly parse the environment.

### `backend/src/db/database.py`

This creates:

- a SQLAlchemy engine with connection-health and pooling options;
- `SessionLocal`, the database-session factory;
- `get_db()`, the request dependency that always closes the session.

Interview explanation:

> A session represents a unit of database work. HTTP requests receive a scoped
> session through dependency injection, while background ingestion creates its
> own session because the request session closes after the response.

## 7. SQLAlchemy models

The models are the relational vocabulary of the system.

| Model | Meaning |
|---|---|
| `User` | Account identity plus stored Google Drive OAuth tokens |
| `UserFolder` | A Drive folder selected by a user and its overall progress |
| `IngestionJob` | One ingestion attempt with totals and failed file IDs |
| `Image` | Drive metadata, processing state, face count, and storage address |
| `Face` | Bounding box, confidence, image link, and Qdrant point ID |
| `SearchQuery` | One query's detection status, latency, and result summary |
| `SearchResult` | Ranked relationship between a query and a matched image/face |
| `PersonCluster` | A grouping concept for faces believed to be the same person |
| `ClusteringJob` | Tracks future or separate face-clustering work |

Why both `UserFolder` and `IngestionJob` exist:

> A folder is a reusable resource selected by the user. A job is one execution
> attempt. Keeping them separate preserves job history and allows the same folder
> to be ingested again.

Why both `Image` and `Face` exist:

> One image can contain zero, one, or many faces. Image metadata belongs on the
> Image row, while each detected bounding box and vector identity belongs on a
> separate Face row.

## 8. Authentication flow

Relevant files:

- `routers/auth.py`: HTTP request models and endpoints.
- `services/auth_service.py`: bcrypt and JWT operations.
- `services/keys.py`: typed authentication settings.
- `frontend/src/lib/auth.ts`: browser-side Google OAuth orchestration.

Flow:

1. The frontend obtains a Google access token.
2. It reads the user's Google profile.
3. It sends the Google token to `/auth/google/session`.
4. The backend creates or updates the User and stores Drive credentials.
5. The backend issues its own access and refresh JWTs.
6. The frontend includes the backend access JWT in protected API calls.
7. `get_current_user()` verifies it and loads the user.

Why issue an application JWT instead of using the Google token everywhere?

> The Google token authorizes Google APIs. The backend JWT represents an
> authenticated application session and contains application-specific token
> types and expiry rules. Separating them reduces coupling to Google and prevents
> external-provider tokens from becoming the app's general authorization model.

`bcrypt` is used for password hashing because it is intentionally slow and uses
a random salt. JWTs are signed with HS256, so the server can verify that claims
were created by the application and were not modified.

## 9. Folder ingestion flow

This is the most important workflow to know.

### Step 1: Register a folder

`POST /ingestion/folders` reaches `routers/ingestion.py`, which calls
`ingestion_service.create_or_update_folder()`. That delegates to
`folder_service.upsert_user_folder()`.

The folder is unique to the user and Drive folder ID. Re-registering it updates
the display name instead of creating duplicates.

### Step 2: Create and schedule a job

`POST /ingestion/folders/{folder_id}/start`:

1. Checks that the folder belongs to the authenticated user.
2. Creates an `IngestionJob` in queued state.
3. Returns HTTP 202 Accepted.
4. Adds a background task that opens a new SQLAlchemy session.

HTTP 202 is appropriate because the work is accepted but not finished.

### Step 3: Discover Drive images

`ingestion/job_runner.py` marks the job and folder as processing, then
`drive_service.list_images_in_folder()` queries Google Drive.

The Drive service:

- fetches direct children only;
- ignores trashed files;
- supports shared drives;
- handles pagination;
- requests only metadata needed by ingestion;
- filters to MIME types beginning with `image/`.

The discovered file count becomes the job and folder total.

### Step 4: Process each file

`ingestion/file_processor.py` executes these steps:

```text
Validate Drive file ID
  -> optionally skip an unchanged completed image
  -> upsert Image metadata and mark processing
  -> download bytes from Drive
  -> optionally upload bytes to Supabase
  -> detect faces and embeddings with InsightFace
  -> replace Postgres Face rows
  -> upsert embeddings into Qdrant
  -> save Qdrant point IDs on Face rows
  -> mark Image done and increment progress
```

Why upsert the Image before external writes?

> It creates a stable image UUID. Supabase object keys and Qdrant payloads can
> then refer to stable relational identities.

Why use `auto_commit=False` in many service calls?

> Lower-level functions stage related changes, and the coordinator commits them
> together. For example, marking an image done and incrementing both progress
> counters should be one relational transaction rather than three independent
> commits.

### Step 5: Retry and finalize

Exceptions from a file are converted into `FileProcessResult` values. This lets
the first pass continue processing the rest of the folder.

`retry.py` performs exactly one retry for initial failures. A bounded retry can
recover transient errors without creating an infinite loop for corrupt images.

After retry:

- permanent failures update job and folder failure counts;
- all-file failure gets a clear terminal error;
- partial failure preserves its failure status and details;
- successful work remains counted.

The outer exception handler rolls back interrupted database work and then writes
terminal failure state in a fresh transaction, preventing jobs from remaining
stuck as “running.”

## 10. Face detection and vector storage

### `services/face_service.py`

Image bytes are decoded with Pillow into RGB. InsightFace expects BGR ordering,
so the channel order is reversed before inference.

For each valid detection the service returns:

- face index within the image;
- bounding-box position and dimensions;
- detector confidence;
- embedding vector.

The InsightFace analyzer is expensive to initialize. `_get_face_analyzer()` uses
lazy initialization and double-checked locking so concurrent requests do not load
the model more than once.

For query photos, `extract_primary_face_embedding()` chooses the face with the
best detection confidence, then uses face area as a secondary preference.

### `services/vector_service.py`

Qdrant stores a point per face:

```text
point ID: face UUID
vector: InsightFace embedding
payload: user_id, face_id, image_id, optional cluster_id
```

Before writing, `ensure_face_collection()` creates the collection or verifies
that its vector size matches the model output. Mixing vector dimensions would
make the collection invalid.

Cosine distance compares vector direction and is commonly used for normalized
embedding similarity. Payload indexes make user and identifier filtering faster.

The query filter includes `user_id` before limiting results. This is important:
filtering after a global search could leak other users' matches or return too few
valid results.

## 11. Search flow

`POST /search` follows this path:

1. `routers/search.py` reads uploaded bytes and validates that they are nonempty.
2. `search_service.create_search_query()` creates history before processing.
3. InsightFace extracts the primary query-face embedding.
4. If there is no face, the query is saved as a successful zero-result search.
5. Qdrant finds the closest vectors filtered by user.
6. `persist_search_results()` validates Qdrant face IDs against Postgres.
7. Valid matches become ranked `SearchResult` rows.
8. The router hydrates image metadata and creates signed Supabase URLs.

Why persist search results instead of returning Qdrant results directly?

> Persistence provides search history, latency and result metrics, stable ranks,
> and relational links to image data. It also prevents malformed or stale Qdrant
> payloads from becoming broken API responses.

Why use `joinedload()`?

> The response needs each result's image and face. Eager loading retrieves those
> relationships with the query instead of triggering repeated database requests,
> avoiding the N+1 query problem.

## 12. Supabase storage flow

`storage_service.upload_image()` creates a stable key:

```text
{user_id}/{image_id}.{extension}
```

Using `upsert` means re-ingestion replaces the object instead of creating
duplicates. Postgres stores this stable path.

The bucket can remain private because `get_signed_url()` creates a temporary URL
only when the frontend needs to display an image. Permanent public URLs would
make access harder to revoke.

Storage is optional in the current pipeline. If it is not configured, image and
face metadata can still be processed, but the frontend cannot receive stored
image URLs.

## 13. Frontend components

### `frontend/src/lib/api.ts`

This is the typed boundary between React and FastAPI. `apiRequest()`:

- joins the backend base URL and path;
- JSON-encodes object bodies;
- leaves `FormData` unchanged for image uploads;
- adds the bearer token;
- converts backend failures into JavaScript errors;
- parses successful JSON responses.

The response types mirror the FastAPI response models, which makes page code
safer and easier to autocomplete.

### `frontend/src/lib/auth.ts`

This loads Google's browser script, requests OAuth scopes, fetches the Google
profile, exchanges the Google access token for backend JWTs, and stores the user
session in browser storage.

### Routes

| Route file | Responsibility |
|---|---|
| `index.tsx` | Landing/login experience |
| `dashboard.tsx` | User photo library and folder selection entry point |
| `progress.tsx` | Polls ingestion progress and displays results |
| `query.tsx` | Upload/camera query and similar-face results |
| `about.tsx` | Product explanation |
| `__root.tsx` | Shared application shell |

TanStack Router generates `routeTree.gen.ts`. Generated code should not be
manually edited because it is rebuilt from route files.

### Reusable frontend pieces

- `use-auth.ts` synchronizes React state with login/logout and browser storage.
- `require-auth.tsx` protects pages that require a session.
- `site-header.tsx` supplies shared navigation and account controls.
- `components/ui/` contains reusable presentation components.
- `photo-store.ts` supports the lightweight browser-side upload flow.

## 14. Important reliability decisions

### Per-file isolation

A corrupt image should fail one `FileProcessResult`, not the whole folder. This
allows useful work to complete and gives accurate partial-progress reporting.

### Transaction ownership

Small state services accept `auto_commit`. Standalone calls commit immediately;
coordinators disable it and commit multiple related state changes atomically.

### Stable cross-system IDs

Postgres Face UUIDs are also Qdrant point IDs. Image UUIDs appear in Supabase
keys and Qdrant payloads. Stable IDs make cross-system tracing and cleanup easier.

### Cached heavyweight clients

Settings, Supabase, Qdrant, and the face analyzer are cached or lazily initialized
to avoid repeated setup cost.

### User ownership checks

Queries filter both the requested resource ID and authenticated user ID. Vector
search also filters on user ID inside Qdrant.

## 15. Limitations and how you would improve them

Be honest about these in an interview; discussing improvements shows engineering
judgment.

### Background tasks are process-local

FastAPI `BackgroundTasks` are simple but not durable. A server restart can lose
in-progress work.

Improvement: move ingestion to Celery, RQ, Dramatiq, or a managed queue with
worker retries and job leases.

### Cross-database operations are not one transaction

Postgres, Supabase, and Qdrant cannot share a normal SQL transaction. A failure
after an external write can temporarily leave orphaned data.

Improvement: use idempotent operations, reconciliation jobs, compensating cleanup,
and an outbox/state-machine pattern.

### Automatic table creation is not a migration system

`create_all()` helps local development but does not version production schema
changes.

Improvement: use Alembic migrations and disable automatic creation in production.

### Face-model errors currently become empty detections

This makes the user experience simple but can hide the difference between “no
face” and “model failure.”

Improvement: return a typed detection result or raise domain-specific exceptions.

### Google token refresh needs production hardening

The Drive client receives stored tokens, but a production system should robustly
refresh expired tokens, encrypt them at rest, and handle revoked consent.

### Local browser storage is limited

It is convenient for session and small preview data but is not appropriate for
large or sensitive persistent datasets.

## 16. Common interviewer questions

### Why FastAPI?

> It provides typed request validation with Pydantic, dependency injection for
> authentication and database sessions, automatic OpenAPI documentation, and
> straightforward async endpoints around blocking work delegated to threads or
> background tasks.

### Why Postgres plus Qdrant?

> Postgres is strong at relationships, ownership, transactions, and reporting.
> Qdrant is designed for nearest-neighbor vector search. Using each for its
> strength is clearer than forcing one system to do both jobs.

### Why copy Drive images to Supabase?

> It gives the application a stable object path and controlled signed URLs,
> instead of depending on Drive rendering permissions and token availability for
> every search-result view.

### How is user data isolated?

> Protected routes resolve the authenticated user, relational queries include
> user ownership, storage keys begin with the user ID, and Qdrant searches apply
> a user-ID payload filter before returning results.

### What happens if one image fails?

> Its relational work is rolled back, failed image state is recorded, processing
> continues for other files, and it receives one retry. Final folder and job
> counters include permanent failures.

### How do you avoid duplicate ingestion?

> Images are upserted by user and Drive file ID. When configured, a completed
> image is skipped if its filename, MIME type, and size still match Drive.
> Supabase and Qdrant writes use stable IDs and upsert behavior.

### How would this scale?

> I would put ingestion behind a durable queue, run multiple workers, batch
> downloads and vector writes where safe, use GPU model workers, add migrations,
> instrument latency/error metrics, and add reconciliation for Postgres, storage,
> and Qdrant consistency.

### How would you test it?

> Unit-test state transitions and pure mapping logic; mock Drive, Supabase,
> InsightFace, and Qdrant at service boundaries; integration-test repositories
> against test containers; test FastAPI endpoints with dependency overrides; and
> run one end-to-end ingestion fixture through all infrastructure in CI.

## 17. A good live code-walk order

If an interviewer asks you to share the code, follow this order:

1. `README.MD` architecture and data flow.
2. `backend/src/app.py` to show router registration.
3. `backend/src/routers/ingestion.py` to show the API boundary.
4. `backend/src/services/ingestion_service.py` to show the facade.
5. `backend/src/ingestion/job_runner.py` for folder orchestration.
6. `backend/src/ingestion/file_processor.py` for the core pipeline.
7. `backend/src/services/face_service.py` for model inference.
8. `backend/src/services/vector_service.py` for vector storage/search.
9. `backend/src/services/search_service.py` for the reverse search flow.
10. `frontend/src/lib/api.ts` and one route to show frontend integration.

This order tells one coherent story instead of opening unrelated files.

## 18. Final one-minute explanation

> The application uses a layered architecture. React handles the user experience
> and talks only to FastAPI. FastAPI routers validate requests and authentication,
> services contain business and integration logic, and the ingestion package
> coordinates long-running folder and image workflows. Google Drive is the input
> source, InsightFace converts faces into embeddings, Postgres stores application
> state, Qdrant performs vector similarity search, and Supabase stores displayable
> image objects. Stable UUIDs link the systems. Processing is isolated per file,
> retries are bounded, and progress is persisted. The current implementation is
> suitable as a clear working system; the next production step would be a durable
> queue, migrations, stronger token handling, observability, and reconciliation
> across the three persistence systems.
