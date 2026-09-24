# FaceSeek: Complete Project Questions and Answers

This document explains the current repository as implemented. It covers the main product flows, small implementation details, operational behavior, edge cases, and known gaps. When this document says â€œcurrently,â€ it refers to the code in this repository, not a planned feature.

## 1. Project purpose and scope

### 1. What is this project?

It is a full-stack face-search application. A user signs in with Google, selects a Google Drive folder, ingests its images, extracts face embeddings, and searches their own image library using another face photo.

### 2. Is it a general image classifier?

Not in the usual sense. Despite the repository name, the implemented ML feature is face detection and face-similarity search. It does not currently assign general labels such as â€œdog,â€ â€œcar,â€ or â€œlandscape.â€

### 3. What are the main features?

- Google authentication and Google Drive access
- Drive folder registration
- Folder-based image ingestion
- Face detection and 512-dimensional face embeddings
- Image and job progress tracking
- User-scoped vector similarity search
- Private image storage with temporary signed URLs

### 4. What is outside the current scope?

Video ingestion, recursive folder traversal, general object classification, manual face labeling, a complete clustering workflow, administrative screens, user deletion, password-based production authentication, and a finished production deployment topology are not implemented.

### 5. What are the main technologies?

The backend uses FastAPI, SQLAlchemy, Postgres, InsightFace, Qdrant, Supabase Storage, Google Drive API, JWTs, and optionally Celery with Redis.

## 2. High-level architecture

### 6. What are the major runtime components?

```text
FastAPI API
   |    |       |          |
   |    |       |          +--> InsightFace / ONNX Runtime
   |    |       +-------------> Qdrant
   |    +---------------------> Supabase Storage
   +--------------------------> Postgres
        |
        +---------------------> Google Drive API
```

In production-style job execution, FastAPI also sends work through Redis to a separate Celery worker.

### 7. How is the backend organized?

- `routers/` handles HTTP, validation, authentication, and response shapes.
- `services/` contains reusable business logic and external integrations.
- `ingestion/` coordinates folder and per-file ingestion.
- `models/` defines SQLAlchemy/Postgres records.
- `db/` contains configuration, the engine, and session handling.
- `tasks.py` exposes the Celery task.

### 8. What is the FastAPI entry point?

`backend/main.py` imports `create_app()` from `backend/src/app.py` and exposes the resulting `app` object for Uvicorn.

## 3. Complete user flow

### 9. What happens during a normal Drive-based workflow?

1. A valid Google access token is exchanged for backend JWTs.
2. A Drive folder is registered in Postgres.
3. An ingestion job is created.
4. The worker lists direct image children in the folder.
5. Each image is downloaded, optionally stored, analyzed, and persisted.
6. Job progress is read from Postgres through the status endpoint.
7. A query image is submitted to the search endpoint.
8. InsightFace selects a primary face.
9. Qdrant finds similar faces belonging to that user.
10. Postgres resolves the matched face and image records.
11. Supabase generates temporary image URLs.

### 10. Does selecting a folder immediately ingest it?

No. Folder registration and ingestion start are separate API operations.

### 11. Does the application recursively scan subfolders?

No. It lists only direct children of the selected Drive folder. A child folder is not recursively traversed.

### 12. Are non-image Drive files ingested?

No. The Drive listing keeps only items whose MIME type starts with `image/`.

## 4. Authentication and authorization

### 13. How does Google sign-in become a backend session?

A caller sends the Google access token to `POST /auth/google/session`. The backend calls Googleâ€™s user-info endpoint, trusts the verified response rather than caller-supplied identity fields, creates or updates the user, stores Drive tokens, and returns backend access and refresh JWTs.

### 14. Why does the backend call Google user-info?

It prevents a caller from simply claiming another email or Google ID. The token must be accepted by Google and return an email.

### 15. What information is stored for a Google user?

Email, display name, avatar URL, Google subject ID, Drive access token, optional Drive refresh token, status, and timestamps are stored in Postgres.

### 16. Are Google tokens encrypted at rest by this application?

No application-level encryption is implemented. They are stored as text in Postgres. Production deployment must protect the database and should add token encryption or a secret/token vault.

### 17. What do backend JWTs contain?

They contain a `sub` holding the user UUID, a token `type` (`access` or `refresh`), and an expiration.

### 18. How long do backend tokens last?

The defaults are 30 minutes for access tokens and 7 days for refresh tokens. They are controlled by `ACCESS_TOKEN_EXPIRE_MINUTES` and `REFRESH_TOKEN_EXPIRE_DAYS`.

### 19. Can a refresh token call protected APIs?

No. The authentication dependency explicitly requires `type=access`.

### 20. What happens if a JWT user no longer exists or is inactive?

Protected requests return HTTP 401.

### 21. Does the project support email-only login?

Yes, but it is deliberately marked insecure. `/auth/register` and `/auth/login` require only an email and are enabled only when `ALLOW_INSECURE_EMAIL_AUTH=true`.

### 22. Should email-only login be enabled in production?

No. Production validation requires `ALLOW_INSECURE_EMAIL_AUTH=false`, which hides those endpoints behind HTTP 404.

### 23. Are the email-only routes password-based?

No. Password hashing helpers exist in `auth_service.py`, but the current register/login routes do not accept or verify passwords.

### 24. How is authorization enforced between users?

Protected routes resolve the authenticated user from the access JWT. Folder, job, image, and search queries are filtered by that userâ€™s UUID. Qdrant searches also filter on the `user_id` payload before applying the result limit.

### 25. Can one user request another userâ€™s job or search by UUID?

No. The database query includes both the resource UUID and current user UUID, so it returns 404 if ownership does not match.

### 26. Is refresh-token rotation implemented?

No. `/auth/refresh` validates the existing refresh token and returns a new access token only.

### 27. Is logout revocation implemented server-side?

No token denylist or revocation store is implemented. Issued JWTs remain valid until expiration.

## 5. Google Drive behavior

### 28. Which Google Drive permission is expected?

The documentation recommends the read-only Drive scope: `https://www.googleapis.com/auth/drive.readonly`.

### 29. How is the Drive client created?

The backend loads the userâ€™s stored access and refresh tokens into Google `Credentials` and builds a Drive v3 client.

### 30. Does the application handle Drive pagination?

Yes. It requests up to 1,000 items per page and follows `nextPageToken` until exhausted.

### 31. Does it support shared drives?

The list request enables `includeItemsFromAllDrives` and `supportsAllDrives`. Actual access still depends on the userâ€™s token and permissions.

### 32. Which Drive metadata is collected?

File ID, name, MIME type, size, width, height, and image capture time are requested.

### 33. What happens when the Drive token is missing?

Drive service creation raises an error, and the ingestion job is ultimately marked failed.

### 34. Does this code explicitly refresh expired Google access tokens?

It supplies the stored refresh token to Google credentials, but it does not supply OAuth client credentials or persist newly refreshed tokens in this service. Reliable long-lived refresh behavior therefore needs additional production work.

### 35. How much Drive listing data is logged?

Counts are logged, along with a bounded sample of up to 20 item names and MIME types for diagnosis.

## 6. Ingestion jobs and background workers

### 36. Why is ingestion performed as a background job?

Downloading and analyzing a folder may take much longer than a normal HTTP request. The API creates a durable job record and returns HTTP 202 quickly, allowing progress to be retrieved separately.

### 37. What job states exist?

The database enum contains `queued`, `running`, `done`, `failed`, and `cancelled`.

### 38. Is cancellation implemented?

The enum supports `cancelled`, but there is no cancellation API or worker cancellation logic.

### 39. What are the two task execution modes?

- `background`: FastAPI schedules an in-process background task.
- `celery`: FastAPI enqueues a task for a separate Celery worker through Redis.

### 40. Does an in-process background task block the start request?

No. The start route returns the queued job first. However, the work still shares the API processâ€™s CPU, memory, database pool, and failure lifecycle.

### 41. Can in-process work affect other requests?

Yes. InsightFace is CPU-heavy, and Drive, storage, Qdrant, and Postgres use shared resources. Other requests can become slower even though the original start response is non-blocking.

### 42. Why is Celery preferred in production?

It isolates ingestion from API processes, supports a durable broker, and allows independent worker scaling and restart behavior.

### 43. What Celery reliability settings are enabled?

Tasks acknowledge late, reject on worker loss, prefetch one task per worker slot, track the started state, and retry broker connection on startup.

### 44. Does Celery guarantee exactly-once execution?

No. Late acknowledgment improves recovery but can cause a task to execute again after worker loss. The ingestion code therefore relies on stable identifiers, upserts, replacement behavior, and the skip setting to reduce duplicate effects.

### 45. Why does every background mode create a new database session?

The request-scoped session closes after the HTTP response. A worker-owned session prevents use of a closed connection and cleanly bounds transaction ownership.

### 46. What happens if Celery enqueueing fails?

The job is marked failed with â€œCould not enqueue ingestion job,â€ and the API returns HTTP 503.

### 47. What happens if the FastAPI process stops during an in-process task?

The task is lost. The persisted job may remain running unless another reconciliation mechanism updates it; no reconciliation scheduler is currently implemented.

### 48. What Redis databases are used by default?

The example uses Redis database 0 as the Celery broker and database 1 as the Celery result backend.

### 49. Does the application read Celery result records for job progress?

No. Progress comes from the Postgres ingestion job, not the Celery result backend.

### 50. How is progress retrieved?

The caller keeps the returned job ID and requests `GET /ingestion/jobs/{job_id}`. The backend exposes persisted Postgres counters; it does not provide WebSockets or server-sent events.

### 51. What counters are tracked?

Jobs track total, processed, failed, and failed Drive file IDs. Folder records track total images, processed images, and failed images.

### 52. How does a job determine its total?

After Drive discovery, the number of direct image files becomes both the job total and folder total.

### 53. Are files processed concurrently inside one job?

No. The current `process_drive_files` flow processes them sequentially.

### 54. Are failed files retried?

Yes. Failed files receive one immediate retry pass. Permanently bad files do not loop forever.

### 55. Can one bad file abort the entire folder immediately?

Normally no. Per-file work is isolated and failures are collected for the retry pass.

### 56. When is an entire job considered failed?

An unhandled workflow exception marks it failed. If all files fail, it is explicitly failed. Partial failures also preserve an error message, causing the final status helper to keep the job/folder in `failed` rather than `done`.

### 57. What happens for an empty folder?

The total becomes zero, no files are processed, and the job completes successfully unless another error occurs.

### 58. What does `job_type` currently change?

The API and database preserve it, and the standard value is `full`, but there is no separate partial/delta algorithm keyed by this value.

## 7. Per-image ingestion

### 59. What happens to each Drive image?

The pipeline upserts its Postgres image record, marks it processing, downloads bytes, enforces the ingestion size limit, optionally uploads it to Supabase, detects faces, replaces Postgres face rows, upserts embeddings to Qdrant, stores Qdrant IDs, and marks the image complete.

### 60. What is the default maximum ingestion image size?

25 MiB (`26214400` bytes), controlled by `MAX_INGESTION_IMAGE_BYTES`.

### 61. Is size checked before or after Drive download?

The bytes must first be downloaded from Drive; the configured limit is then enforced before further processing.

### 62. What makes an image unique?

Postgres enforces uniqueness on `(user_id, drive_file_id)`.

### 63. What makes a tracked folder unique?

Postgres enforces uniqueness on `(user_id, drive_folder_id)`.

### 64. What does `SKIP_ALREADY_INGESTED` do?

When enabled, an already completed image is skipped if its relevant Drive metadata still matches. The job and folder processed counters still advance for that file.

### 65. What happens when an existing Drive image changes?

The metadata comparison prevents the unchanged-file shortcut, allowing it to be processed again.

### 66. Can the same Drive file belong to two selected folders for one user?

The image uniqueness rule permits only one image row per user and Drive file ID. Its folder association can therefore represent only one current folder row.

### 67. How are per-file transactions handled?

Image, face, folder counter, and job counter changes are coordinated with caller-owned commits so the state for a processed file advances together. On failure, the transaction is rolled back before failure state is persisted.

### 68. What happens if no face is found in a valid image?

The image can still finish successfully with `face_count=0`; it simply contributes no face vectors for search.

### 69. What happens when InsightFace throws during detection?

The detector wrapper returns an empty detection list. This generally makes the image a successful zero-face image rather than a failed image, so model failures may be indistinguishable from genuinely face-free images.

### 70. Does re-ingestion duplicate face rows?

No. Existing face rows for the image are deleted and replaced before the new rows are committed.

### 71. Does re-ingestion delete stale Qdrant points when the new image has fewer faces?

No explicit deletion of old Qdrant points is visible in the current ingestion flow. Reused face UUIDs are not guaranteed after face-row replacement, so orphaned points are a possible cleanup gap. Search filters invalid points when Postgres resolution fails.

### 72. Are original image dimensions stored?

Width and height fields exist and Drive metadata is requested for them.

### 73. Is EXIF capture time stored?

The `taken_at` field is populated from Driveâ€™s image media metadata time when available.

## 8. Face detection and embeddings

### 74. Which face model is used?

InsightFace `buffalo_l`.

### 75. Which runtime executes the model?

ONNX Runtime.

### 76. What is the embedding dimension?

The expected InsightFace embedding length is 512.

### 77. How is image color ordering handled?

Pillow decodes the image to RGB, then the NumPy array is reversed to BGR for InsightFace/OpenCV expectations.

### 78. What face information is stored in Postgres?

Person index within the image, bounding box coordinates and dimensions, detection score, Qdrant point ID, optional cluster ID, user ID, and image ID.

### 79. Are embedding vectors stored in Postgres?

No. Postgres stores relational metadata and the Qdrant point ID. Qdrant stores the vectors.

### 80. How is the primary face chosen from a search photo?

The code prefers the face with the strongest detection confidence, then uses face area as a tiebreaker.

### 81. Does a search photo with multiple faces search all faces?

No. Only the selected primary face is searched.

### 82. Is the face analyzer created for every image?

No. It is lazily created once per process and protected by a lock during initialization.

### 83. Where does InsightFace cache its model files?

It uses the process userâ€™s InsightFace cache, commonly `~/.insightface`. The Docker image creates `/home/app/.insightface` for the non-root application user.

## 9. Qdrant vector storage

### 84. What is the default collection name?

`face_embeddings`, controlled by `QDRANT_COLLECTION_NAME`.

### 85. Which distance metric is used?

Cosine distance.

### 86. Is the collection created automatically?

Yes. The vector service lazily creates it when first needed.

### 87. What happens if an existing collection has the wrong vector size?

The service raises an error instead of mixing incompatible embeddings.

### 88. Which payload fields are indexed?

`user_id`, `face_id`, `image_id`, and `cluster_id`.

### 89. What is used as a Qdrant point ID?

The Postgres face UUID, represented as a string.

### 90. What does a Qdrant payload contain?

User ID, face ID, image ID, and optional cluster ID.

### 91. How are users isolated in vector search?

The Qdrant query includes a required `user_id` filter, so other usersâ€™ vectors are excluded before limiting results.

### 92. What happens if Qdrant returns a stale or malformed face ID?

Malformed IDs are ignored. Valid UUIDs that no longer resolve to a Postgres face and image are also ignored.

### 93. Is there a minimum similarity threshold?

No explicit score threshold is applied. The service asks for the nearest `limit` points.

### 94. Is Qdrant optional?

Not for face-vector ingestion or search. Storage can be optional in development, but the vector path expects Qdrant to be reachable.

## 10. Supabase Storage

### 95. What is stored in Supabase?

The raw ingested image bytes.

### 96. Is Supabase storage mandatory in development?

No. If all required storage settings are absent, ingestion can continue without uploading an object. Image preview URLs will then be unavailable.

### 97. Is Supabase mandatory in production configuration?

Yes. Production settings validation requires the URL, service-role key, and bucket.

### 98. How are object keys constructed?

The key is stable: `{user_id}/{image_id}.{extension}`.

### 99. Why use a stable key?

Re-ingestion can overwrite the same object rather than creating orphaned duplicates.

### 100. Is the bucket intended to be public?

No. The backend generates temporary signed URLs for browser display.

### 101. How long do signed URLs last?

The default is 3,600 seconds, or one hour.

### 102. Is a signed URL stored in Postgres?

No. Postgres stores the stable object key and bucket. Signed URLs are generated when building API responses.

### 103. What file extension is used?

It is guessed from the MIME type. `.jpe` is normalized to `.jpg`; unknown types use `.bin`.

### 104. Can storage URLs using `*.storage.supabase.co` be accepted?

The helper normalizes such a host to the standard project API URL expected by the Supabase SDK.

### 105. Is object deletion exposed through an API?

No. A storage deletion helper exists, but no current HTTP endpoint calls it.

## 11. Search

### 106. How is a search submitted?

`POST /search?limit=N` accepts a multipart form field named `image` and requires a bearer access token.

### 107. What result limits are allowed?

The backend allows 1 through 50.

### 108. What is the default query-image size limit?

10 MiB, controlled by `MAX_QUERY_IMAGE_BYTES`.

### 109. How does the backend reject invalid uploads?

It returns 415 for a non-image content type, 413 for an oversized image, and 400 for an empty image.

### 110. What happens if no face is detected in the query?

A search-query history row is still saved with `face_detected=false`, zero results, no top score, and measured latency.

### 111. Is search synchronous or background?

Search is synchronous. The HTTP response waits for face detection, Qdrant search, Postgres persistence, and response hydration.

### 112. Can search affect concurrent requests?

Yes. It uses InsightFace and external services during the request. FastAPI moves the synchronous workflow to a threadpool, which protects the event loop but does not eliminate CPU or infrastructure contention.

### 113. Is search history persisted?

Yes. `search_queries` tracks detection status, count, top score, latency, and timestamps. `search_results` stores ranked face/image matches and scores.

### 114. Can a prior search be retrieved?

Yes, with `GET /search/{query_id}`, provided it belongs to the authenticated user.

### 115. Is the uploaded query image saved to Supabase?

Not by the current search route. The original filename is placed in `query_image_storage_key`, but the bytes are not uploaded by this flow, so the field name is currently misleading.

### 116. Can an already ingested image ID be submitted directly as a query?

No. The current backend search endpoint accepts uploaded image bytes, not an existing image ID. A caller can download available image bytes and upload them to the search endpoint.

### 117. Are duplicate result images possible?

Yes. Qdrant searches faces, not unique images. If multiple faces from the same image are close matches, multiple `search_results` can reference that image.

### 118. How are result ranks assigned?

Valid Qdrant hits are persisted in returned order with ranks starting at 1. Invalid/stale hits are skipped without leaving rank gaps.

## 12. Postgres schema and state

### 119. Which tables exist?

`users`, `user_folders`, `images`, `faces`, `person_clusters`, `ingestion_jobs`, `clustering_jobs`, `search_queries`, and `search_results`.

### 120. What is the source of truth for application metadata?

Postgres is the relational source of truth. Qdrant points are resolved back to Postgres before results are returned.

### 121. What deletion behavior is defined?

Most user-owned records cascade when a user is deleted. Image faces cascade when an image is deleted. An imageâ€™s folder reference becomes null if its folder is deleted. Face cluster references become null if a cluster is deleted.

### 122. Are clustering tables actively used?

Models and schema exist for person clusters and clustering jobs, but no clustering router, worker, or completed clustering service is implemented.

### 123. What is the difference between a folder and an ingestion job?

A folder is reusable tracked state for a Drive location. A job represents one execution attempt and preserves its own counters, failed IDs, errors, and timestamps.

### 124. Why are UUIDs used?

They avoid predictable sequential identifiers and work well across independent services. UUIDs alone are not authorization; all protected queries still enforce ownership.

### 125. Does SQLAlchemy automatically create tables?

In development it can, when `AUTO_CREATE_TABLES=true`. Production validation requires it to be false.

### 126. How should production schema changes be applied?

With versioned Alembic migrations before application startup. An initial migration exists under `backend/alembic/versions/`.

### 127. What is `backend/schema.sql` for?

It is a relational schema reference and manual bootstrap option. Alembic is the intended production evolution mechanism.

### 128. How is the database URL formed?

Settings build a PostgreSQL/psycopg2 URL from host, port, username, password, database, and SSL mode. Username, password, and database values are URL-escaped.

### 129. What database pool settings exist?

The defaults are pool size 5, maximum overflow 10, recycle after 1,800 seconds, and connection pre-ping enabled.

### 130. Why is `expire_on_commit=False` used?

SQLAlchemy model attributes remain available after commits without automatic reloads, which is convenient for response building and multi-step workflows.

## 13. API reference

### 131. Which authentication endpoints exist?

- `POST /auth/register` â€” development-only email registration
- `POST /auth/login` â€” development-only email login
- `POST /auth/google/session` â€” create/update a Google-backed session
- `POST /auth/refresh` â€” exchange a refresh JWT for a new access JWT

### 132. Which ingestion endpoints exist?

- `POST /ingestion/folders` â€” register or rename a userâ€™s Drive folder
- `POST /ingestion/folders/{folder_id}/start` â€” create and schedule a job
- `GET /ingestion/folders/{folder_id}` â€” read folder progress
- `GET /ingestion/jobs/{job_id}` â€” read job progress
- `GET /ingestion/images` â€” list the userâ€™s ingested images

### 133. Which search endpoints exist?

- `POST /search` â€” run a face search
- `GET /search/{query_id}` â€” retrieve a persisted search

### 134. Which health endpoints exist?

- `/health/live` checks that the process can respond.
- `/health` and `/health/ready` execute `SELECT 1` against Postgres.

### 135. Does readiness verify every dependency?

No. It checks Postgres only, not Google, Supabase, Qdrant, Redis, Celery workers, or InsightFace model availability.

### 136. When are Swagger and OpenAPI enabled?

They are enabled outside production when `ENABLE_API_DOCS=true`. Production always disables them through `is_production`.

## 14. Configuration

### 137. Where does backend configuration come from?

Environment variables and `backend/.env`. Existing process environment values take precedence because the custom loader uses `setdefault`.

### 138. Is `backend/.env.example` safe to use unchanged?

No. Placeholder database, JWT, Google, Supabase, and other values must be replaced.

### 139. Which environment names are allowed?

`development`, `test`, and `production`.

### 140. What extra production validation exists?

Production requires migrations instead of auto-create, disables insecure email auth, requires trusted CORS origins, requires Celery and a broker, and requires complete Supabase settings.

### 141. Does production validation require a Celery result backend?

No. It requires the broker URL, but not the result-backend URL.

### 142. Does production validation verify that `SECRET_KEY` is strong?

No. Operators must supply a strong, private value.

### 143. What is `TRUSTED_HOSTS`?

It is a comma-separated allow-list for HTTP Host headers, enforced by Starletteâ€™s trusted-host middleware.

### 144. What is `BACKEND_CORS_ORIGINS`?

It is a comma-separated list of browser origins allowed to call the API. Credentials are enabled, so production rejects a wildcard origin.

### 145. What does `FORCE_HTTPS` do?

It adds HTTPS redirect middleware. It should be configured with awareness of the deployment proxy.

### 146. What does `REQUEST_ID_HEADER` do?

It chooses the header name used to accept or generate a request ID and return it with the response.

## 15. Middleware, logging, and observability

### 147. What middleware is enabled?

Request context/security headers, GZip compression, trusted hosts, optional HTTPS redirect, and CORS.

### 148. Which browser security headers are added?

`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, and a restrictive `Permissions-Policy`.

### 149. When is GZip applied?

For responses of at least 1,000 bytes.

### 150. What is logged for each request?

Method, path, response status, duration in milliseconds, and request ID.

### 151. Where are logs written?

By default to `logs/app.log` and the terminal.

### 152. How does log rotation work?

The file rotates at 5 MiB and retains three backups.

### 153. Can a caller provide its own request ID?

Yes. If the configured request-ID header is present, the middleware reuses it; otherwise it generates a UUID.

### 154. Are secrets intentionally logged?

The code generally logs IDs, counts, paths, and errors rather than tokens. Operators should still review exception logs because external libraries may include sensitive context.

## 16. Error handling and consistency

### 155. What happens when a request database operation fails?

The request-scoped dependency rolls back and re-raises the exception, then always closes the session.

### 156. What happens on an unhandled ingestion exception?

The runner rolls back the interrupted transaction, marks the folder and job failed in a new transaction, and logs the exception.

### 157. Can Postgres and Qdrant/Supabase be updated atomically?

No. They are separate systems with no distributed transaction. Partial external writes are possible if a later step fails.

### 158. How does the code reduce partial-state damage?

It uses stable storage keys, Qdrant upserts, replacement of relational faces, per-file database transactions, failure records, retrying, and Postgres validation of Qdrant results.

### 159. Is there an automated reconciliation or garbage-collection job?

No. Stale Qdrant points, orphaned storage objects, and stuck job states require future maintenance tooling.

### 160. What happens if signed URL generation fails while listing results?

There is no per-result fallback exception handler; the request can fail even though the search records were persisted.

### 161. Does the system provide idempotency keys for start requests?

No. Repeating the start request creates another ingestion job.

### 162. Can two jobs ingest the same folder simultaneously?

There is no explicit per-folder lock. Concurrent jobs can race on image rows, face replacement, counters, and external writes.

### 163. Are counter increments protected against concurrent lost updates?

They are ordinary ORM read/modify/write operations, not atomic SQL increments. Concurrent jobs can produce inaccurate counters.

## 17. Security and privacy

### 164. Which credentials must never be exposed outside trusted backend infrastructure?

Database credentials, backend `SECRET_KEY`, Supabase service-role key, Qdrant API key, Redis credentials, and Google client secret.

### 165. Are images public?

They are intended to live in a private Supabase bucket and be served through expiring signed URLs.

### 166. Is biometric data involved?

Yes. Face embeddings and face-location metadata are biometric-adjacent sensitive data. A real deployment needs consent, retention, deletion, access-control, legal, and breach-response policies appropriate to its jurisdiction.

### 167. Is there a user data export or deletion API?

No.

### 168. Is rate limiting implemented?

No. Authentication, search, ingestion starts, and status polling are not rate-limited in application code.

### 169. Is malware scanning implemented for images?

No. MIME type and size checks exist for search uploads, and Pillow decodes images, but there is no malware scanning service.

### 170. Are MIME types sufficient to prove a file is a valid image?

No. MIME types are caller/provider metadata. Actual decoding provides some additional validation, but production systems should treat uploaded content as untrusted.

### 171. Is a Content Security Policy set?

No CSP header is added by the current backend middleware.

## 18. Performance and scaling

### 172. What are the main expensive operations?

InsightFace inference, Drive downloads, Supabase uploads, Qdrant operations, signed URL generation, and database queries.

### 173. Can more Celery workers always make ingestion faster?

No. Excess workers may exhaust CPU, RAM, database connections, Drive quotas, Qdrant capacity, or storage bandwidth.

### 174. Why is Celery prefetch set to one?

It avoids one worker reserving many long-running image jobs and improves fairness.

### 175. Does one folder job use multiple Celery tasks per image?

No. One Celery task runs the whole folder job; per-image work is called inside it.

### 176. What are the implications of one task per folder?

It is simple and keeps folder state coordinated, but very large folders create long-running tasks and do not parallelize individual images.

### 177. Does Drive listing load all image metadata into memory?

Yes. Pagination controls API calls, but the final list is accumulated before processing so totals can be established.

### 178. Are signed URLs generated in batches?

No. The backend generates them one result/image at a time.

### 179. Does the API use async libraries for external services?

Most integrations are synchronous. FastAPI routes use `run_in_threadpool` around blocking workflows where needed.

## 19. Development and testing

### 180. How is the backend installed?

Create a Python virtual environment and install `backend/requirements.txt`.

### 181. How is the backend started locally?

From `backend/`, run `uvicorn main:app --reload`.

### 182. Which backend checks are documented?

Python compilation and unittest discovery:

```powershell
.\.venv\Scripts\python.exe -m compileall -q backend
Set-Location backend
..\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

### 183. What do the existing backend tests cover?

They cover app creation/health behavior, configuration validation, and important folder/job state transitions. They do not form a complete integration or end-to-end suite.

### 184. Are Google, Supabase, Qdrant, InsightFace, and Celery flows covered end to end?

No complete end-to-end test suite for all those services is present.

### 185. Why might the first InsightFace run be slow?

The model analyzer is initialized lazily and model files may need to be downloaded or loaded into memory.

## 20. Deployment and containers

### 186. What does the backend Dockerfile do?

It uses Python 3.12 slim, installs native libraries needed by image/model dependencies, installs Python packages, copies the backend, creates a non-root `app` user, prepares log/model directories, adds a liveness health check, and starts Uvicorn.

### 187. Does the Dockerfile start a Celery worker?

No. A separate container/process command is needed for Celery workers.

### 188. Does the repository contain a Docker Compose stack?

No Compose file is currently present.

### 189. What does the container health check call?

`http://127.0.0.1:8000/health/live`, which verifies only that the API process responds.

### 190. Why does the container run as a non-root user?

It limits the impact of a process compromise and follows container security best practice.

### 191. Why are proxy headers enabled in the container command?

They allow Uvicorn to interpret forwarded client/protocol information when deployed behind a trusted reverse proxy. The current command accepts forwarded headers broadly, so network-level proxy trust must be configured carefully.

### 192. What services are needed for a production-style deployment?

At minimum: FastAPI API instances, Postgres, Redis, one or more Celery workers, Qdrant, Supabase Storage, Google OAuth configuration, secret management, monitoring, backups, and a reverse proxy/load balancer as appropriate.

## 21. Small but important implementation details

### 193. Why does the query upload read one extra byte?

Reading `max_bytes + 1` distinguishes a file exactly at the limit from an oversized one without buffering an unlimited body.

### 194. Why are blocking database/service calls moved to a threadpool in async routes?

They would otherwise block the event loop and delay unrelated async request handling.

### 195. Why are models imported during app assembly?

Importing `src.models` registers all SQLAlchemy model tables with the declarative metadata before optional table creation.

### 196. Why is the Qdrant client cached?

It avoids repeatedly creating network clients. The Supabase client and InsightFace analyzer are similarly reused.

### 197. Why are results reloaded with joined relationships?

The response needs result, face, and image data after persistence. Eager loading avoids repeated per-result database queries and prevents missing relationship data.

### 198. What sorting is used for the image library?

Newest ingestion time first, with Drive filename ascending as a secondary order.

### 199. Why can a folder or job end as failed after some successful files?

Final helpers preserve a recorded error message. The data remains useful, but the terminal state signals that the run was not completely successful.

### 200. Are logs created even if console logging is disabled?

Yes. A rotating file handler is always configured.

### 201. What happens when `LOG_LEVEL` is invalid?

Logging falls back to `INFO`.

### 202. Does `get_settings()` notice environment changes while the process is running?

No. It is cached per process. Restart the API/worker after configuration changes.

### 203. Does each API process have its own model and client caches?

Yes. Cached settings, Qdrant/Supabase clients, and the InsightFace analyzer are process-local.

### 204. Why is production behavior stricter than development?

Development defaults favor easy startup. Production validation prevents several known unsafe conveniences, though it is not a complete security guarantee.

## 22. Known gaps and recommended next work

### 205. What are the highest-priority production gaps?

- Encrypt or vault stored Google tokens.
- Add robust Google token refresh and persistence.
- Run ingestion exclusively through managed Celery/Redis.
- Add stuck-job reconciliation and worker monitoring.
- Prevent concurrent jobs for the same folder.
- Add Qdrant and storage cleanup/reconciliation.
- Add rate limits and abuse controls.
- Implement complete user data deletion.
- Add refresh-token rotation and server-side revocation.
- Add end-to-end and external-service integration tests.
- Add metrics, tracing, alerts, backups, and recovery procedures.

### 206. What data-consistency improvement is most important?

Define explicit reconciliation rules across Postgres, Qdrant, and Supabase. No transaction can atomically cover all three, so cleanup and repair jobs are necessary.

### 207. What worker improvement is most important?

Add job leases/heartbeats and a reconciliation process that marks or retries jobs left `queued` or `running` after process failure.

### 208. What ingestion scalability improvement is most important?

For large folders, consider a parent job that discovers files and creates bounded per-file tasks, while preserving idempotency, rate limits, counter accuracy, and final aggregation.

### 209. What search-quality improvements are possible?

Add a similarity threshold, optional multi-face query selection, image deduplication, calibration/evaluation data, and explicit handling of poor-quality or ambiguous faces.

### 210. What privacy improvement is most important?

Implement informed consent, retention limits, auditable deletion across every store, encrypted credentials, and documented handling of face embeddings.

### 211. What naming improvements would reduce confusion?

Rename the project or describe it as face search rather than general image classification, and rename or implement the currently misleading `query_image_storage_key` behavior.

## 23. Quick troubleshooting

### 212. Why does the API fail at startup with missing settings?

Required database settings have no safe defaults. Create `backend/.env` and supply valid Postgres values.

### 213. Why does Google login work but Drive ingestion fail?

The token may lack Drive scope, be expired, not have access to the folder, or lack reliable refresh configuration. Sign in again after changing OAuth scopes.

### 214. Why are no Drive files discovered?

The folder may contain only subfolders/non-images, the images may not be direct children, MIME metadata may not start with `image/`, or the user may lack access.

### 215. Why is a job stuck at queued?

In Celery mode, verify Redis, worker startup, queue routing, and worker logs. In background mode, verify the API process remained alive.

### 216. Why is a job stuck at running?

The worker may have stopped unexpectedly, an external call may be hanging, or the process may have died before failure state was persisted. There is no automatic stuck-job reconciler.

### 217. Why are images processed but previews missing?

Supabase may be unconfigured, upload may not have occurred, the object/key may be missing, or signed URL generation may be failing.

### 218. Why does search return zero results?

The query may contain no detectable face, the user may have no successfully embedded faces, Qdrant may be empty/unreachable, or stale points may be discarded during Postgres resolution.

### 219. Why can search return an unexpected person?

Nearest-neighbor search always returns closest available vectors when no threshold is set. Face angle, lighting, resolution, occlusion, model bias, and a small library can all reduce accuracy.

### 220. Why does the first ingestion/search consume significant memory?

The `buffalo_l` InsightFace model is loaded into the process and image arrays are decoded in memory. Worker concurrency must be sized accordingly.

## 24. Final mental model

### 221. What is the shortest accurate explanation of the whole project?

```text
Google identifies the user and supplies Drive access.
Postgres records ownership and workflow state.
The worker downloads and analyzes Drive images.
Supabase stores private image bytes.
InsightFace turns faces into embeddings.
Qdrant finds nearby embeddings for the same user.
FastAPI enforces the boundaries and returns hydrated results.
API callers retrieve persisted job progress and search results.
```

### 222. What is the single most important architectural rule?

Every resource and vector search must remain scoped to the authenticated user, while Postgres remains the relational source of truth and external systems are treated as reconcilable secondary stores.
