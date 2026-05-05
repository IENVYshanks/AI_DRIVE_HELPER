from functools import lru_cache
from urllib.parse import quote_plus

from pydantic import computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.ext.declarative import declarative_base

from src.config_env import get_env_path, load_env_file

load_env_file()

Base = declarative_base()


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    AUTO_CREATE_TABLES: bool = True
    SKIP_ALREADY_INGESTED: bool = True

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

    SUPABASE_URL: str | None = None
    SUPABASE_SERVICE_ROLE_KEY: str | None = None
    SUPABASE_STORAGE_BUCKET: str | None = None

    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str | None = None
    QDRANT_COLLECTION_NAME: str = "face_embeddings"

    model_config = SettingsConfigDict(
        env_file=str(get_env_path()),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_production_settings(self):
        if self.ENVIRONMENT.lower() == "production" and self.AUTO_CREATE_TABLES:
            raise ValueError("AUTO_CREATE_TABLES must be false in production")
        return self

    @computed_field
    @property
    def DATABASE_URI(self) -> str:
        username = quote_plus(self.DB_USERNAME)
        password = quote_plus(self.DB_PASSWORD)
        database = quote_plus(self.DB_NAME)
        return(
            f"postgresql+psycopg2://{username}:"
            f"{password}@{self.DATABASE_HOST}:"
            f"{self.DB_PORT}/{database}?sslmode={self.DB_SSLMODE}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
