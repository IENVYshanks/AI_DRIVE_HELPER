"""Durable ingestion tasks executed by Celery workers in production."""

from uuid import UUID

from celery import Celery

from src.db.config import get_settings
from src.db.database import SessionLocal
from src.services.ingestion_service import run_ingestion_job


settings = get_settings()
celery_app = Celery(
    "ai_image_classifier",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)
celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    broker_connection_retry_on_startup=True,
)


@celery_app.task(name="ingestion.run_folder")
def run_folder_ingestion_task(job_id: str) -> None:
    """Run a folder job with a worker-owned database session."""
    db = SessionLocal()
    try:
        run_ingestion_job(db, job_id=UUID(job_id))
    finally:
        db.close()
