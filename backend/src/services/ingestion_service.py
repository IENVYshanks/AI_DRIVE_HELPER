from __future__ import annotations

from sqlalchemy.orm import Session

from src.ingestion.job_runner import run_ingestion_job
from src.models.image import Image
from src.models.ingestion_job import IngestionJob
from src.models.user_folder import UserFolder
from src.services.folder_service import upsert_user_folder
from src.services.job_service import create_ingestion_job


def create_or_update_folder(
    db: Session,
    *,
    user_id,
    drive_folder_id: str,
    folder_name: str | None = None,
) -> UserFolder:
    return upsert_user_folder(
        db,
        user_id=user_id,
        drive_folder_id=drive_folder_id,
        folder_name=folder_name,
    )


def start_ingestion_job(
    db: Session,
    *,
    user_id,
    folder_id,
    job_type: str = "full",
) -> IngestionJob:
    return create_ingestion_job(db, user_id=user_id, folder_id=folder_id, job_type=job_type)


def get_folder_for_user(db: Session, *, folder_id, user_id) -> UserFolder | None:
    return (
        db.query(UserFolder)
        .filter(UserFolder.id == folder_id, UserFolder.user_id == user_id)
        .first()
    )


def get_job_for_user(db: Session, *, job_id, user_id) -> IngestionJob | None:
    return (
        db.query(IngestionJob)
        .filter(IngestionJob.id == job_id, IngestionJob.user_id == user_id)
        .first()
    )


def get_all_images_for_user(db: Session, *, user_id) -> list[Image]:
    return (
        db.query(Image)
        .filter(Image.user_id == user_id)
        .order_by(Image.ingested_at.desc(), Image.drive_file_name.asc())
        .all()
    )
