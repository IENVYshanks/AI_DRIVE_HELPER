"""Typed environment configuration and SQLAlchemy declarative base."""

from functools import lru_cache
import re
from urllib.parse import quote_plus

from pydantic import computed_field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.orm import declarative_base

from src.config_env import get_env_path, load_env_file

load_env_file()

Base = declarative_base()


class Settings(BaseSettings):
    """Application settings loaded from environment variables or backend/.env."""
    ENVIRONMENT: str = "development"
    AUTO_CREATE_TABLES: bool = True
    SKIP_ALREADY_INGESTED: bool = True
    ENABLE_API_DOCS: bool = True
    FORCE_HTTPS: bool = False
    TRUSTED_HOSTS: str = "localhost,127.0.0.1"

    DATABASE_HOST: str = "localhost"
    DB_USERNAME: str
    DB_PASSWORD: str
    DB_PORT: int = 5432
    DB_NAME: str
    DB_SSLMODE: str = "require"
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_RECYCLE_SECONDS: int = 1800

    LOG_LEVEL: str = "INFO"
    LOG_FILE_PATH: str = "logs/app.log"
    LOG_TO_CONSOLE: bool = True
    BACKEND_CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    REQUEST_ID_HEADER: str = "X-Request-ID"
    SESSION_COOKIE_SECURE: bool = False
    SESSION_COOKIE_SAMESITE: str = "lax"
    MAX_QUERY_IMAGE_BYTES: int = 10 * 1024 * 1024
    MAX_INGESTION_IMAGE_BYTES: int = 25 * 1024 * 1024
    MAX_IMAGE_WIDTH: int = 12_000
    MAX_IMAGE_HEIGHT: int = 12_000
    MAX_IMAGE_PIXELS: int = 40_000_000
    MAX_IMAGE_FRAMES: int = 1
    MAX_DRIVE_FOLDER_ITEMS: int = 5_000
    MAX_INGESTION_FILES_PER_JOB: int = 1_000
    MAX_ACTIVE_INGESTION_JOBS_PER_USER: int = 2
    MAX_SEARCHES_PER_USER_PER_MINUTE: int = 10
    MAX_CONCURRENT_FACE_INFERENCES: int = 2
    FACE_INFERENCE_WAIT_SECONDS: int = 30
    TASK_QUEUE_MODE: str = "background"
    CELERY_BROKER_URL: str | None = None
    CELERY_RESULT_BACKEND: str | None = None

    SUPABASE_URL: str | None = None
    SUPABASE_SERVICE_ROLE_KEY: str | None = None
    SUPABASE_STORAGE_BUCKET: str | None = None

    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None
    GOOGLE_REDIRECT_URI: str | None = None
    OAUTH_TOKEN_ENCRYPTION_KEYS: str = ""
    OAUTH_TOKEN_ACTIVE_KEY_ID: str = ""

    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str | None = None
    QDRANT_COLLECTION_NAME: str = "face_embeddings"

    model_config = SettingsConfigDict(
        env_file=str(get_env_path()),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        """Reject development conveniences and incomplete services in production."""
        if self.ENVIRONMENT.lower() != "production":
            return self

        errors: list[str] = []
        if self.AUTO_CREATE_TABLES:
            errors.append("AUTO_CREATE_TABLES must be false")
        if "*" in self.cors_origins:
            errors.append("BACKEND_CORS_ORIGINS cannot contain '*' when credentials are enabled")
        if not self.cors_origins:
            errors.append("BACKEND_CORS_ORIGINS must contain at least one trusted origin")
        if not self.SESSION_COOKIE_SECURE:
            errors.append("SESSION_COOKIE_SECURE must be true")
        if self.TASK_QUEUE_MODE != "celery":
            errors.append("TASK_QUEUE_MODE must be celery")
        if not self.CELERY_BROKER_URL:
            errors.append("CELERY_BROKER_URL is required")

        storage_values = (
            self.SUPABASE_URL,
            self.SUPABASE_SERVICE_ROLE_KEY,
            self.SUPABASE_STORAGE_BUCKET,
        )
        if not all(storage_values):
            errors.append("all Supabase storage settings are required")

        google_oauth_values = (
            self.GOOGLE_CLIENT_ID,
            self.GOOGLE_CLIENT_SECRET,
            self.GOOGLE_REDIRECT_URI,
        )
        if not all(google_oauth_values):
            errors.append("all Google OAuth settings are required")

        try:
            encryption_keys = self.oauth_token_encryption_keys
        except ValueError as exc:
            errors.append(str(exc))
        else:
            if not encryption_keys:
                errors.append("OAUTH_TOKEN_ENCRYPTION_KEYS is required")
            if self.OAUTH_TOKEN_ACTIVE_KEY_ID not in encryption_keys:
                errors.append("OAUTH_TOKEN_ACTIVE_KEY_ID must select a configured key")

        if errors:
            raise ValueError("Invalid production configuration: " + "; ".join(errors))
        return self

    @field_validator("ENVIRONMENT")
    @classmethod
    def validate_environment(cls, value: str) -> str:
        """Restrict environment names so production checks cannot be misspelled."""
        normalized = value.strip().lower()
        if normalized not in {"development", "test", "production"}:
            raise ValueError("ENVIRONMENT must be development, test, or production")
        return normalized

    @field_validator("TASK_QUEUE_MODE")
    @classmethod
    def validate_task_queue_mode(cls, value: str) -> str:
        """Allow only the implemented ingestion execution modes."""
        normalized = value.strip().lower()
        if normalized not in {"background", "celery"}:
            raise ValueError("TASK_QUEUE_MODE must be background or celery")
        return normalized

    @field_validator("SESSION_COOKIE_SAMESITE")
    @classmethod
    def validate_cookie_samesite(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"lax", "strict", "none"}:
            raise ValueError("SESSION_COOKIE_SAMESITE must be lax, strict, or none")
        return normalized

    @field_validator(
        "MAX_QUERY_IMAGE_BYTES",
        "MAX_INGESTION_IMAGE_BYTES",
        "MAX_IMAGE_WIDTH",
        "MAX_IMAGE_HEIGHT",
        "MAX_IMAGE_PIXELS",
        "MAX_IMAGE_FRAMES",
        "MAX_DRIVE_FOLDER_ITEMS",
        "MAX_INGESTION_FILES_PER_JOB",
        "MAX_ACTIVE_INGESTION_JOBS_PER_USER",
        "MAX_SEARCHES_PER_USER_PER_MINUTE",
        "MAX_CONCURRENT_FACE_INFERENCES",
        "FACE_INFERENCE_WAIT_SECONDS",
    )
    @classmethod
    def validate_upload_limits(cls, value: int) -> int:
        """Require positive resource limits so they cannot be accidentally disabled."""
        if value <= 0:
            raise ValueError("image byte limits must be positive")
        return value

    @computed_field
    @property
    def DATABASE_URI(self) -> str:
        """Build an escaped SQLAlchemy Postgres connection string."""
        username = quote_plus(self.DB_USERNAME)
        password = quote_plus(self.DB_PASSWORD)
        database = quote_plus(self.DB_NAME)
        return (
            f"postgresql+psycopg2://{username}:"
            f"{password}@{self.DATABASE_HOST}:"
            f"{self.DB_PORT}/{database}?sslmode={self.DB_SSLMODE}"
        )

    @property
    def cors_origins(self) -> list[str]:
        """Convert the comma-separated environment value into middleware input."""
        return [
            origin.strip()
            for origin in self.BACKEND_CORS_ORIGINS.split(",")
            if origin.strip()
        ]

    @property
    def trusted_hosts(self) -> list[str]:
        """Convert the trusted Host header allow-list into middleware input."""
        return [host.strip() for host in self.TRUSTED_HOSTS.split(",") if host.strip()]

    @property
    def is_production(self) -> bool:
        """Return whether strict production behavior should be enabled."""
        return self.ENVIRONMENT == "production"

    @property
    def oauth_token_encryption_keys(self) -> dict[str, bytes]:
        """Parse key-id/hex-key pairs used for OAuth credential encryption."""
        keys: dict[str, bytes] = {}
        for raw_entry in self.OAUTH_TOKEN_ENCRYPTION_KEYS.split(","):
            entry = raw_entry.strip()
            if not entry:
                continue
            key_id, separator, hex_key = entry.partition(":")
            if not separator or not re.fullmatch(r"[A-Za-z0-9._-]+", key_id):
                raise ValueError("OAuth token encryption key entries are invalid")
            if key_id in keys:
                raise ValueError("OAuth token encryption key IDs must be unique")
            try:
                key = bytes.fromhex(hex_key)
            except ValueError as exc:
                raise ValueError("OAuth token encryption keys must be hexadecimal") from exc
            if len(key) != 32:
                raise ValueError("OAuth token encryption keys must contain 32 bytes")
            keys[key_id] = key
        return keys


@lru_cache
def get_settings() -> Settings:
    """Load settings once per process so every integration sees one snapshot."""
    return Settings()
