CREATE EXTENSION IF NOT EXISTS pgcrypto;

DROP TABLE IF EXISTS search_results CASCADE;
DROP TABLE IF EXISTS search_queries CASCADE;
DROP TABLE IF EXISTS clustering_jobs CASCADE;
DROP TABLE IF EXISTS ingestion_jobs CASCADE;
DROP TABLE IF EXISTS faces CASCADE;
DROP TABLE IF EXISTS person_clusters CASCADE;
DROP TABLE IF EXISTS images CASCADE;
DROP TABLE IF EXISTS user_folders CASCADE;
DROP TABLE IF EXISTS access_grants CASCADE;
DROP TABLE IF EXISTS image_faces CASCADE;
DROP TABLE IF EXISTS persons CASCADE;
DROP TABLE IF EXISTS drive_tokens CASCADE;
DROP TABLE IF EXISTS users CASCADE;

DROP TYPE IF EXISTS user_status CASCADE;
DROP TYPE IF EXISTS job_status CASCADE;
DROP TYPE IF EXISTS process_status CASCADE;

CREATE TYPE user_status AS ENUM ('active', 'suspended', 'deleted');
CREATE TYPE job_status AS ENUM ('queued', 'running', 'done', 'failed', 'cancelled');
CREATE TYPE process_status AS ENUM ('pending', 'processing', 'done', 'failed');

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    name TEXT,
    avatar_url TEXT,

    google_id TEXT UNIQUE,
    drive_access_token TEXT,
    drive_refresh_token TEXT,
    token_expires_at TIMESTAMPTZ,

    status user_status DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE user_folders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    drive_folder_id TEXT NOT NULL,
    folder_name TEXT,

    status process_status DEFAULT 'pending',
    total_images INT DEFAULT 0,
    processed_images INT DEFAULT 0,
    failed_images INT DEFAULT 0,
    error_message TEXT,

    selected_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(user_id, drive_folder_id)
);

CREATE TABLE images (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    folder_id UUID REFERENCES user_folders(id) ON DELETE SET NULL,

    drive_file_id TEXT NOT NULL,
    drive_file_name TEXT,

    storage_key TEXT,
    storage_bucket TEXT,
    file_size_bytes BIGINT,
    mime_type TEXT,

    width INT,
    height INT,
    taken_at TIMESTAMPTZ,

    status process_status DEFAULT 'pending',
    face_count INT DEFAULT 0,
    error_message TEXT,

    ingested_at TIMESTAMPTZ DEFAULT NOW(),
    processed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(user_id, drive_file_id)
);

CREATE TABLE person_clusters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    label TEXT,
    thumbnail_face_id UUID,

    face_count INT DEFAULT 0,
    image_count INT DEFAULT 0,

    last_clustered_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE faces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    image_id UUID NOT NULL REFERENCES images(id) ON DELETE CASCADE,

    person_idx INT NOT NULL,

    bbox_x FLOAT,
    bbox_y FLOAT,
    bbox_w FLOAT,
    bbox_h FLOAT,

    detection_score FLOAT,
    qdrant_point_id TEXT,
    cluster_id UUID REFERENCES person_clusters(id) ON DELETE SET NULL,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE person_clusters
ADD CONSTRAINT fk_thumbnail_face
FOREIGN KEY (thumbnail_face_id)
REFERENCES faces(id)
ON DELETE SET NULL;

CREATE TABLE search_queries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    query_image_storage_key TEXT,
    face_detected BOOLEAN DEFAULT false,

    results_count INT DEFAULT 0,
    top_score FLOAT,
    search_latency_ms INT,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE search_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_id UUID NOT NULL REFERENCES search_queries(id) ON DELETE CASCADE,
    image_id UUID NOT NULL REFERENCES images(id) ON DELETE CASCADE,
    face_id UUID REFERENCES faces(id) ON DELETE SET NULL,

    similarity_score FLOAT,
    rank INT,
    feedback TEXT,

    UNIQUE(query_id, rank)
);

CREATE TABLE ingestion_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    folder_id UUID REFERENCES user_folders(id) ON DELETE CASCADE,

    status job_status DEFAULT 'queued',
    job_type TEXT DEFAULT 'full',

    total INT DEFAULT 0,
    processed INT DEFAULT 0,
    failed INT DEFAULT 0,

    error_message TEXT,
    failed_file_ids TEXT[],

    queued_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE clustering_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    status job_status DEFAULT 'queued',

    faces_processed INT DEFAULT 0,
    clusters_created INT DEFAULT 0,
    clusters_merged INT DEFAULT 0,

    queued_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
