from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.models.image import Image


def mark_image_processing(db: Session, image: Image, *, auto_commit: bool = True) -> Image:
    image.status = "processing"
    image.error_message = None
    image.updated_at = datetime.now(timezone.utc)
    if auto_commit:
        db.commit()
        db.refresh(image)
    return image


def mark_image_done(
    db: Session,
    image: Image,
    *,
    face_count: int,
    auto_commit: bool = True,
) -> Image:
    image.status = "done"
    image.face_count = face_count
    image.error_message = None
    image.processed_at = datetime.now(timezone.utc)
    image.updated_at = datetime.now(timezone.utc)
    if auto_commit:
        db.commit()
        db.refresh(image)
    return image


def mark_image_failed(
    db: Session,
    image: Image,
    *,
    error_message: str,
    auto_commit: bool = True,
) -> Image:
    image.status = "failed"
    image.error_message = error_message
    image.updated_at = datetime.now(timezone.utc)
    if auto_commit:
        db.commit()
        db.refresh(image)
    return image


def set_image_storage_location(
    db: Session,
    image: Image,
    *,
    storage_key: str,
    storage_bucket: str,
    auto_commit: bool = True,
) -> Image:
    image.storage_key = storage_key
    image.storage_bucket = storage_bucket
    image.updated_at = datetime.now(timezone.utc)
    if auto_commit:
        db.commit()
        db.refresh(image)
    return image
