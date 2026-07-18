"""Image lifecycle transitions shared by the ingestion pipeline.

Functions can either commit immediately or participate in a larger transaction
through ``auto_commit=False``. The file processor uses the latter so image,
folder, and job state advance atomically.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.models.image import Image
from src.services._persistence import commit_and_refresh

def mark_image_processing(db: Session, image: Image, *, auto_commit: bool = True) -> Image:
    """Mark an image as actively being processed."""
    image.status = "processing"
    image.error_message = None
    image.updated_at = datetime.now(timezone.utc)
    return commit_and_refresh(db, image, auto_commit=auto_commit)

def mark_image_done(
    db: Session,
    image: Image,
    *,
    face_count: int,
    auto_commit: bool = True,
) -> Image:
    """Mark an image as successfully processed and record its face count."""
    image.status = "done"
    image.face_count = face_count
    image.error_message = None
    image.processed_at = datetime.now(timezone.utc)
    image.updated_at = datetime.now(timezone.utc)
    return commit_and_refresh(db, image, auto_commit=auto_commit)

def mark_image_failed(
    db: Session,
    image: Image,
    *,
    error_message: str,
    auto_commit: bool = True,
) -> Image:
    """Mark an image as failed and retain a user-visible error message."""
    image.status = "failed"
    image.error_message = error_message
    image.updated_at = datetime.now(timezone.utc)
    return commit_and_refresh(db, image, auto_commit=auto_commit)

def set_image_storage_location(
    db: Session,
    image: Image,
    *,
    storage_key: str,
    storage_bucket: str,
    auto_commit: bool = True,
) -> Image:
    """Attach the object-storage address used to retrieve an image."""
    image.storage_key = storage_key
    image.storage_bucket = storage_bucket
    image.updated_at = datetime.now(timezone.utc)
    return commit_and_refresh(db, image, auto_commit=auto_commit)
