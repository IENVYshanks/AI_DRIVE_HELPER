# FaceSeek

FaceSeek is a full-stack face-similarity search application that:

- authenticates users with Google in the React frontend
- browses Google Drive folders
- ingests image files into a backend pipeline
- extracts face embeddings with InsightFace
- stores vectors in Qdrant
- stores app metadata in Postgres
- stores image files in Supabase Storage
- lets users query similar faces using either an uploaded photo or one of their already ingested photos

## Creator

Built and maintained by [Ronit](https://github.com/IENVYshanks).

- Email: [sawaiyanronit12@gmail.com](mailto:sawaiyanronit12@gmail.com)
- LinkedIn: [Ronit Sawaiyan](https://www.linkedin.com/in/ronit-sawaiyan-2b283918a)
- Source: [github.com/IENVYshanks/ai_image_classifier](https://github.com/IENVYshanks/ai_image_classifier)
- Live app: [ai-drive-helper.vercel.app](https://ai-drive-helper.vercel.app/)

## Stack

- Frontend: React / Vite in `frontend/`
- Backend: FastAPI in `backend/`
- Database: Postgres
- Object storage: Supabase Storage
- Vector database: Qdrant
- Face model: InsightFace (`buffalo_l`)

## Features

- Google sign-in with Drive access
- Google Drive folder browsing
- Folder-based ingestion for image files
- Per-image ingestion status tracking
- Face detection and embedding extraction
- Vector similarity search with Qdrant
- Search using:
  - a freshly uploaded query image
  - an already ingested photo from the user library
- Result photo rendering with signed Supabase URLs

## Project Structure

```text
.
|-- backend/
|   |-- main.py
|   |-- requirements.txt
|   |-- schema.sql
|   |-- .env.example
|   `-- src/
|       |-- config_env.py
|       |-- app.py
|       |-- db/
|       |-- dependencies.py
|       |-- ingestion/
|       |-- logging_config.py
|       |-- models/
|       |-- routers/
|       `-- services/
`-- frontend/
    |-- package.json
    |-- vite.config.ts
    `-- src/
```

Important modules:

- [backend/main.py](./backend/main.py): FastAPI app entrypoint
- [backend/src/app.py](./backend/src/app.py): FastAPI app assembly and route registration
- [backend/schema.sql](./backend/schema.sql): relational schema reference
- [backend/src/routers/ingestion.py](./backend/src/routers/ingestion.py): ingestion APIs
- [backend/src/routers/search.py](./backend/src/routers/search.py): face search APIs
- [backend/src/services/ingestion_service.py](./backend/src/services/ingestion_service.py): ingestion pipeline
- [backend/src/services/face_service.py](./backend/src/services/face_service.py): InsightFace integration
- [backend/src/services/vector_service.py](./backend/src/services/vector_service.py): Qdrant integration
- [backend/src/services/storage_service.py](./backend/src/services/storage_service.py): Supabase Storage integration
- [frontend/src](./frontend/src): React frontend source

## Architecture

### How a request moves through the project

The backend is organized in layers so each file has one main responsibility:

1. `routers/` validates HTTP input, authenticates the caller, and shapes the response.
2. `services/` contains reusable business operations and integrations with Drive,
   Supabase, Qdrant, InsightFace, and Postgres.
3. `ingestion/job_runner.py` coordinates a whole folder; `file_processor.py` coordinates
   one image; `state.py` maps Drive metadata and failures into database rows.
4. `models/` defines the Postgres records shared by those layers.
5. The React frontend calls the routers through `frontend/src/lib/api.ts`; it does not
   communicate with databases or storage providers directly.

The ingestion data flow is:

```text
React -> FastAPI router -> ingestion job -> Google Drive download
                                      |-> Supabase image object
                                      |-> InsightFace detection
                                      |-> Postgres image/face/job state
                                      `-> Qdrant face embedding
```

The search flow reverses that relationship: InsightFace embeds the uploaded query,
Qdrant finds similar face IDs, Postgres resolves those IDs to image metadata, and
Supabase provides temporary signed URLs for the response.

### Postgres

Postgres stores application state:

- users
- selected folders
- ingestion jobs
- ingested images
- detected faces
- search queries
- search results

### Qdrant

Qdrant stores one vector per detected face in the `face_embeddings` collection.

Expected collection setup:

- vector size: `512`
- distance: `Cosine`
- payload indexes:
  - `user_id`
  - `face_id`
  - `image_id`
  - `cluster_id`

### Supabase Storage

Supabase Storage stores ingested image files. The backend returns signed URLs so results can be rendered in the UI.

## Environment Variables

Copy `backend/.env.example` to `backend/.env` and `frontend/.env.example` to `frontend/.env.local`, then fill in the values.

### Database

```env
DATABASE_HOST=localhost
DB_USERNAME=postgres
DB_PASSWORD=your_db_password_here
DB_PORT=5432
DB_NAME=postgres
```

### Supabase Storage

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
SUPABASE_STORAGE_BUCKET=images
```

### Qdrant

```env
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=
QDRANT_COLLECTION_NAME=face_embeddings
```

### Backend sessions

```env
SECRET_KEY=your_secret_key_here
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
SESSION_COOKIE_SECURE=false
SESSION_COOKIE_SAMESITE=lax
```

The backend stores revocable session records and sends authentication tokens only in
`HttpOnly` cookies. Set `SESSION_COOKIE_SECURE=true` in production. For local HTTP
development, open both frontend and backend through the same hostname (for example,
`localhost`) so browsers accept the same-site cookies.

### Image and workload limits

```env
MAX_QUERY_IMAGE_BYTES=10485760
MAX_INGESTION_IMAGE_BYTES=26214400
MAX_IMAGE_WIDTH=12000
MAX_IMAGE_HEIGHT=12000
MAX_IMAGE_PIXELS=40000000
MAX_IMAGE_FRAMES=1
MAX_DRIVE_FOLDER_ITEMS=5000
MAX_INGESTION_FILES_PER_JOB=1000
MAX_ACTIVE_INGESTION_JOBS_PER_USER=2
MAX_SEARCHES_PER_USER_PER_MINUTE=10
MAX_GOOGLE_OAUTH_ATTEMPTS_PER_IP_PER_MINUTE=10
MAX_CONCURRENT_FACE_INFERENCES=2
FACE_INFERENCE_WAIT_SECONDS=30
```

Drive downloads are streamed into a bounded buffer. Actual image format, dimensions,
pixel count, and frame count are checked before face inference. Tune these limits for
the memory and CPU available to each backend or worker process.

### Frontend to backend

```env
BACKEND_URL=http://localhost:8000
BACKEND_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

### Google

```env
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_REDIRECT_URI=http://localhost:5173
OAUTH_TOKEN_ENCRYPTION_KEYS=primary:replace_with_64_hex_characters
OAUTH_TOKEN_ACTIVE_KEY_ID=primary
```

For the React frontend, also set:

```env
VITE_BACKEND_URL=http://localhost:8000
VITE_GOOGLE_CLIENT_ID=your_google_client_id.apps.googleusercontent.com
VITE_ENABLE_GOOGLE_AUTH=false
```

Set `VITE_ENABLE_GOOGLE_AUTH=true` to show the landing-page **Continue with
Google** action. Keep it `false` to hide that action across the UI. Vite reads
this flag at startup, so restart the frontend development server after changing
it. The flag controls frontend visibility only; production access control must
continue to be enforced by the backend.

In Google Cloud Console, add these authorized JavaScript origins for local React development:

```text
http://localhost:5173
http://127.0.0.1:5173
```

Use the same Google OAuth client ID in the backend and React configuration. Keep the
client secret backend-only. Configure `GOOGLE_REDIRECT_URI` as an authorized JavaScript
origin in Google Cloud Console; the popup flow sends its one-time authorization code to
the backend, which exchanges it for Google tokens. Generate the OAuth credential-encryption
key with `python -c "import secrets; print(secrets.token_hex(32))"`. Keep the active key and
any previous decryption keys in a secret manager; removing an old key before its stored
tokens have rotated makes those credentials unreadable.

## Installation

Create and activate a virtual environment, then install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
```

Install frontend dependencies from the React app directory:

```powershell
Set-Location frontend
npm install
```

## Database Schema

Apply your schema to Postgres before running the backend. Existing installations must
configure OAuth token encryption keys, then run the Alembic migrations that create the
`auth_sessions` table, add the active-job uniqueness guard, and encrypt existing Google
Drive credentials:

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m alembic upgrade head
```

This project expects the schema represented in [backend/schema.sql](./backend/schema.sql).

## Running the App

### Start the React frontend and FastAPI backend together

From the repository root, run:

```powershell
npm run dev
```

Press `Ctrl+C` to stop both processes. The individual commands below are still
available when you only need one part of the app. The combined development
launcher explicitly uses FastAPI's in-process background-task mode for ingestion,
so Redis and a Celery worker are not required locally. Production continues to
require `TASK_QUEUE_MODE=celery` and a durable Redis broker.

### 1. Start FastAPI

```powershell
.\.venv\Scripts\Activate.ps1
Set-Location backend
uvicorn main:app --reload
```

Backend docs:

- Swagger UI: `http://localhost:8000/docs`

### 2. Start React Frontend

In a second terminal:

```powershell
Set-Location frontend
npm run dev
```

React frontend:

- Vite app: `http://localhost:5173`

## Development Checks

Run the backend syntax and state-transition checks from the repository root:

```powershell
.\.venv\Scripts\python.exe -m compileall -q backend
Set-Location backend
..\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Run the complete frontend check from `frontend/`:

```powershell
npm run check
```

This performs TypeScript checking, ESLint validation, and a production build. Formatting is
kept separate: use `npm run format:check` to inspect it or `npm run format` to apply it.

## Typical Flow

1. Sign in with Google.
2. Browse Google Drive and pick a folder.
3. Start ingestion.
4. The backend:
   - lists image files in the selected folder
   - downloads image bytes from Google Drive
   - uploads images to Supabase Storage
   - extracts faces and embeddings with InsightFace
   - writes metadata to Postgres
   - writes vectors to Qdrant
5. After ingestion, query with:
   - an uploaded photo
   - or one of your ingested photos
6. View search results in:
   - a result table
   - a photo gallery tab

## Notes on Search

- Search is user-scoped.
- Qdrant queries are filtered by `user_id`.
- Search result records are persisted in Postgres.
- Result images are displayed using signed Supabase Storage URLs.

## Logging

Logs are written to the configured rotating log file and, by default, the terminal.

Default:

```env
LOG_FILE_PATH=logs/app.log
LOG_LEVEL=INFO
```

## Security Notes

- Never commit `.env`
- Rotate any Google, Supabase, Qdrant, or database credentials if they were ever exposed
- Keep `SUPABASE_SERVICE_ROLE_KEY` backend-only
- Keep every configured OAuth token-encryption key in a secret manager until all values
  written with that key have been rotated to the active key

## Current Limitations

- The app currently focuses on image-only ingestion
- The Google Drive browser intentionally ignores non-image file types
- Search depends on successful ingestion and available signed image URLs
- Production deployment still needs normal hardening such as migrations, background job infrastructure, and secret management

## License

This project is distributed under the terms in [LICENSE](./LICENSE).
