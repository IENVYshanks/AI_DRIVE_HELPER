"""Load authentication secrets without coupling auth logic to configuration."""

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.config_env import get_env_path, load_env_file

load_env_file()

class Token(BaseSettings):
    """JWT settings with stricter validation in production."""

    ENVIRONMENT: str = "development"
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    SECRET_KEY: str
    REFRESH_TOKEN_EXPIRE_DAYS: int

    model_config = SettingsConfigDict(
        env_file=str(get_env_path()),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_secret(self) -> "Token":
        """Require sufficient signing entropy for production JWTs."""
        if self.ENVIRONMENT.lower() == "production" and len(self.SECRET_KEY) < 32:
            raise ValueError("SECRET_KEY must contain at least 32 characters in production")
        return self


@lru_cache
def get_tokens() -> Token:
    """Load and cache JWT settings."""
    return Token()
