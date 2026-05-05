import logging
from logging import StreamHandler
from logging.handlers import RotatingFileHandler
from pathlib import Path

from fastapi import FastAPI
from sqlalchemy import text

from src.db.database import engine
from src.db.config import Base, get_settings
from src.routers.auth import router as auth_router
from src.routers.ingestion import router as ingestion_router
from src.routers.search import router as search_router
from src import models  

settings = get_settings()
log_file_path = Path(settings.LOG_FILE_PATH)
log_file_path.parent.mkdir(parents=True, exist_ok=True)

log_handlers: list[logging.Handler] = [
    RotatingFileHandler(
        log_file_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    ),
]
if settings.LOG_TO_CONSOLE:
    log_handlers.append(StreamHandler())

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    handlers=log_handlers,
)

if settings.AUTO_CREATE_TABLES:
    Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI Image Classifier API")
app.include_router(auth_router)
app.include_router(ingestion_router)
app.include_router(search_router)


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ok"}
