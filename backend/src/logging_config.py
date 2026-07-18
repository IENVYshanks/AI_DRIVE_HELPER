"""Application logging setup."""

import logging
from logging import StreamHandler
from logging.handlers import RotatingFileHandler
from pathlib import Path

from src.db.config import Settings


def configure_logging(settings: Settings) -> None:
    """Configure bounded file logging and optional console output."""
    log_file_path = Path(settings.LOG_FILE_PATH)
    log_file_path.parent.mkdir(parents=True, exist_ok=True)

    handlers: list[logging.Handler] = [
        RotatingFileHandler(
            log_file_path,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
    ]
    if settings.LOG_TO_CONSOLE:
        handlers.append(StreamHandler())

    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        handlers=handlers,
        force=True,
    )
