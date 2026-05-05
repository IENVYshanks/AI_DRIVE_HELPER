# AI Image Classifier

AI Image Classifier is a full-stack face search application that:

- authenticates users with Google in Streamlit
- browses Google Drive folders
- ingests image files into a backend pipeline
- extracts face embeddings with InsightFace
- stores vectors in Qdrant
- stores app metadata in Postgres
- stores image files in Supabase Storage
- lets users query similar faces using either an uploaded photo or one of their already ingested photos

## Stack

- Frontend: Streamlit
- Backend: FastAPI
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
|-- frontend.py
|-- main.py
|-- requirements.txt
|-- schema.sql
|-- .env.example
|-- .streamlit/
|   `-- secrets.toml
`-- src/
    |-- config_env.py
    |-- db/
    |-- dependencies.py
    |-- models/
    |-- routers/
    `-- services/
```

Important modules:

- [frontend.py](./frontend.py): Streamlit UI
- [main.py](./main.py): FastAPI app entrypoint
- [schema.sql](./schema.sql): relational schema reference
- [src/routers/ingestion.py](./src/routers/ingestion.py): ingestion APIs
- [src/routers/search.py](./src/routers/search.py): face search APIs
- [src/services/ingestion_service.py](./src/services/ingestion_service.py): ingestion pipeline
- [src/services/face_service.py](./src/services/face_service.py): InsightFace integration
- [src/services/vector_service.py](./src/services/vector_service.py): Qdrant integration
- [src/services/storage_service.py](./src/services/storage_service.py): Supabase Storage integration

## Architecture

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

Copy `.env.example` to `.env` and fill in the values.

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

### JWT / backend auth

```env
SECRET_KEY=your_secret_key_here
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
```

### Frontend to backend

```env
BACKEND_URL=http://127.0.0.1:8000
```

### Google

```env
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_API_KEY=your_google_api_key
```

## Streamlit Secrets

The Streamlit login flow is configured in `.streamlit/secrets.toml`.

Important notes:

- use `drive.readonly` if you want to browse Drive folders and files
- restart Streamlit and sign in again after changing OAuth scopes
- do not commit `.streamlit/secrets.toml`

Example shape:

```toml
[auth]
redirect_uri = "http://localhost:8501/oauth2callback"
cookie_secret = "your-cookie-secret"
expose_tokens = ["access"]

[auth.google]
client_id = "your-google-client-id"
client_secret = "your-google-client-secret"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
client_kwargs = { scope = "openid profile email https://www.googleapis.com/auth/drive.readonly", access_type = "offline", prompt = "consent" }
```

## Installation

Create and activate a virtual environment, then install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Database Schema

Apply your schema to Postgres before running the backend.

This project expects the schema represented in [schema.sql](./schema.sql).

## Running the App

### 1. Start FastAPI

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn main:app --reload
```

Backend docs:

- Swagger UI: `http://127.0.0.1:8000/docs`

### 2. Start Streamlit

In a second terminal:

```powershell
.\.venv\Scripts\Activate.ps1
streamlit run frontend.py
```

Frontend:

- Streamlit app: `http://localhost:8501`

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

Logs are written to the configured log file path instead of the terminal.

Default:

```env
LOG_FILE_PATH=logs/app.log
LOG_LEVEL=INFO
```

## Security Notes

- Never commit `.env`
- Never commit `.streamlit/secrets.toml`
- Rotate any Google, Supabase, Qdrant, or database credentials if they were ever exposed
- Keep `SUPABASE_SERVICE_ROLE_KEY` backend-only

## Current Limitations

- The app currently focuses on image-only ingestion
- The Google Drive browser intentionally ignores non-image file types
- Search depends on successful ingestion and available signed image URLs
- Production deployment still needs normal hardening such as migrations, background job infrastructure, and secret management

## License

Add a license before publishing publicly.
