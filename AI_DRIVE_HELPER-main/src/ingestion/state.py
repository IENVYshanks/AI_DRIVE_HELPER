from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.ingestion.results import FileProcessResult
from src.models.image import Image
from src.models.ingestion_job import IngestionJob
from src.models.user_folder import UserFolder
from src.services.folder_service import increment_folder_failed
from src.services.image_service import mark_image_failed
from src.services.job_service import increment_job_failed

logger = logging.getLogger(__name__)


def upsert_image_from_drive_file(
    db: Session,
    *,
    user_id,
    folder_id,
    drive_file: dict,
    auto_commit: bool = True,
) -> Image:
    image = (
        db.query(Image)
        .filter(Image.user_id == user_id, Image.drive_file_id == drive_file["id"])
        .first()
    )
    metadata = drive_file.get("imageMediaMetadata") or {}
    taken_at = _parse_drive_datetime(metadata.get("time"))
    file_size = drive_file.get("size")
    file_size_bytes = int(file_size) if file_size is not None else None

    if image is None:
        image = Image(
            user_id=user_id,
            folder_id=folder_id,
            drive_file_id=drive_file["id"],
        )
        db.add(image)

    image.folder_id = folder_id
    image.drive_file_name = drive_file.get("name")
    image.mime_type = drive_file.get("mimeType")
    image.file_size_bytes = file_size_bytes
    image.width = metadata.get("width")
    image.height = metadata.get("height")
    image.taken_at = taken_at
    image.status = "pending"
    image.error_message = None
    image.updated_at = datetime.now(timezone.utc)

    if auto_commit:
        db.commit()
        db.refresh(image)
    else:
        db.flush()
    return image


def get_existing_image_for_drive_file(
    db: Session,
    *,
    user_id,
    drive_file_id: str,
) -> Image | None:
    return (
        db.query(Image)
        .filter(Image.user_id == user_id, Image.drive_file_id == drive_file_id)
        .first()
    )


def image_matches_drive_file(image: Image, drive_file: dict) -> bool:
    file_size = drive_file.get("size")
    file_size_bytes = int(file_size) if file_size is not None else None
    return (
        image.drive_file_name == drive_file.get("name")
        and image.mime_type == drive_file.get("mimeType")
        and image.file_size_bytes == file_size_bytes
    )


def mark_drive_file_failed(
    db: Session,
    *,
    job: IngestionJob,
    folder: UserFolder,
    drive_file: dict,
    error_message: str,
) -> None:
    if not drive_file.get("id"):
        return

    try:
        image = upsert_image_from_drive_file(
            db,
            user_id=job.user_id,
            folder_id=folder.id,
            drive_file=drive_file,
            auto_commit=False,
        )
        mark_image_failed(db, image, error_message=error_message, auto_commit=False)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception(
            "Could not persist failed image state for drive_file_id=%s job_id=%s",
            drive_file.get("id"),
            job.id,
        )


def record_final_failures(
    db: Session,
    *,
    job: IngestionJob,
    folder: UserFolder,
    failures: list[FileProcessResult],
) -> None:
    if not failures:
        return

    for failure in failures:
        increment_job_failed(
            db,
            job,
            file_id=failure.drive_file.get("id"),
            error_message=failure.error_message,
            auto_commit=False,
        )
        increment_folder_failed(
            db,
            folder,
            error_message=failure.error_message,
            auto_commit=False,
        )
    db.commit()


def _parse_drive_datetime(value: str | None):
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None
