"""Public service facade used by ingestion API routes.

Routers import this module instead of knowing about lower-level folder/job
services or the ingestion runner. The small facade keeps HTTP concerns in the
router and business workflow concerns in the ingestion package.
"""

from __future__ import annotations

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from src.db.config import get_settings
from src.ingestion.job_runner import run_ingestion_job
from src.models.image import Image
from src.models.ingestion_job import IngestionJob
from src.models.user_folder import UserFolder
from src.services.drive_service import (
    FOLDER_MIME_TYPE,
    DriveFolderMetadata,
    get_folder_metadata,
    list_child_folders,
)
from src.services.folder_service import upsert_user_folder
from src.services.job_service import create_ingestion_job

ACTIVE_JOB_STATUSES = ("queued", "running")


class DuplicateIngestionJobError(ValueError):
    """Raised when a folder already has active work for the same user."""


class IngestionQuotaExceededError(ValueError):
    """Raised when a user reaches the configured active-job limit."""


class DriveFolderBrowserError(ValueError):
    """Raised when a requested Drive location is not a folder."""


def browse_drive_folders(
    db: Session,
    *,
    user_id,
    parent_id: str,
) -> tuple[DriveFolderMetadata, list[DriveFolderMetadata]]:
    """Return one Drive folder and its direct child folders."""
    if parent_id == "root":
        current: DriveFolderMetadata = {
            "id": "root",
            "name": "My Drive",
            "parent_id": None,
        }
    else:
        metadata = get_folder_metadata(parent_id, user_id, db)
        if metadata.get("mimeType") != FOLDER_MIME_TYPE:
            raise DriveFolderBrowserError("The selected Drive item is not a folder")
        current = {
            "id": metadata["id"],
            "name": metadata.get("name") or "Untitled folder",
            "parent_id": next(iter(metadata.get("parents", [])), None),
        }
    return current, list_child_folders(parent_id, user_id, db)


def create_or_update_folder(
    db: Session,
    *,
    user_id,
    drive_folder_id: str,
    folder_name: str | None = None,
) -> UserFolder:
    """Register a user's Drive folder or update its display name."""
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
    """Create a queued job only when duplicate and per-user limits allow it."""
    active_for_folder = (
        db.query(IngestionJob)
        .filter(
            IngestionJob.user_id == user_id,
            IngestionJob.folder_id == folder_id,
            IngestionJob.status.in_(ACTIVE_JOB_STATUSES),
        )
        .first()
    )
    if active_for_folder is not None:
        raise DuplicateIngestionJobError("An ingestion job is already active for this folder")

    active_job_count = (
        db.query(IngestionJob)
        .filter(
            IngestionJob.user_id == user_id,
            IngestionJob.status.in_(ACTIVE_JOB_STATUSES),
        )
        .count()
    )
    if active_job_count >= get_settings().MAX_ACTIVE_INGESTION_JOBS_PER_USER:
        raise IngestionQuotaExceededError("Active ingestion job quota exceeded")
    try:
        return create_ingestion_job(
            db,
            user_id=user_id,
            folder_id=folder_id,
            job_type=job_type,
        )
    except IntegrityError as exc:
        db.rollback()
        raise DuplicateIngestionJobError(
            "An ingestion job is already active for this folder"
        ) from exc


def get_folder_for_user(db: Session, *, folder_id, user_id) -> UserFolder | None:
    """Fetch a folder only when it belongs to the requesting user."""
    return (
        db.query(UserFolder)
        .filter(UserFolder.id == folder_id, UserFolder.user_id == user_id)
        .first()
    )


def get_job_for_user(db: Session, *, job_id, user_id) -> IngestionJob | None:
    """Fetch an ingestion job only when it belongs to the requesting user."""
    return (
        db.query(IngestionJob)
        .filter(IngestionJob.id == job_id, IngestionJob.user_id == user_id)
        .first()
    )


def get_all_images_for_user(db: Session, *, user_id) -> list[Image]:
    """Return a user's library with newest ingestions first."""
    return (
        db.query(Image)
        .filter(Image.user_id == user_id)
        .order_by(Image.ingested_at.desc(), Image.drive_file_name.asc())
        .all()
    )
