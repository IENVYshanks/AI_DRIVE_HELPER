"""Persistence operations for a user's tracked Google Drive folder.

Folder counters summarize child image processing for progress APIs. Transition
functions support caller-owned transactions through ``auto_commit=False``.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.models.user_folder import UserFolder
from src.services._persistence import commit_and_refresh


def upsert_user_folder(
    db: Session,
    *,
    user_id,
    drive_folder_id: str,
    folder_name: str | None = None,
) -> UserFolder:
    """Create a tracked Drive folder or update its display name."""
    folder = (
        db.query(UserFolder)
        .filter(
            UserFolder.user_id == user_id,
            UserFolder.drive_folder_id == drive_folder_id,
        )
        .first()
    )
    if folder is None:
        folder = UserFolder(
            user_id=user_id,
            drive_folder_id=drive_folder_id,
            folder_name=folder_name,
        )
        db.add(folder)
    elif folder_name:
        folder.folder_name = folder_name

    db.commit()
    db.refresh(folder)
    return folder


def mark_folder_processing(
    db: Session,
    folder: UserFolder,
    *,
    auto_commit: bool = True,
) -> UserFolder:
    """Reset progress and mark a folder as actively processing."""
    now = datetime.now(timezone.utc)
    folder.status = "processing"
    folder.started_at = now
    folder.completed_at = None
    folder.error_message = None
    folder.processed_images = 0
    folder.failed_images = 0
    folder.updated_at = now
    return commit_and_refresh(db, folder, auto_commit=auto_commit)


def set_folder_total_images(
    db: Session,
    folder: UserFolder,
    total_images: int,
    *,
    auto_commit: bool = True,
) -> UserFolder:
    """Set the number of images discovered in a folder."""
    folder.total_images = total_images
    folder.updated_at = datetime.now(timezone.utc)
    return commit_and_refresh(db, folder, auto_commit=auto_commit)


def increment_folder_processed(
    db: Session,
    folder: UserFolder,
    count: int = 1,
    *,
    auto_commit: bool = True,
) -> UserFolder:
    """Increase the folder's successful-image count."""
    folder.processed_images = (folder.processed_images or 0) + count
    folder.updated_at = datetime.now(timezone.utc)
    return commit_and_refresh(db, folder, auto_commit=auto_commit)


def increment_folder_failed(
    db: Session,
    folder: UserFolder,
    *,
    error_message: str | None = None,
    count: int = 1,
    auto_commit: bool = True,
) -> UserFolder:
    """Increase the failure count and optionally retain the latest error."""
    folder.failed_images = (folder.failed_images or 0) + count
    if error_message:
        folder.error_message = error_message
    folder.updated_at = datetime.now(timezone.utc)
    return commit_and_refresh(db, folder, auto_commit=auto_commit)


def mark_folder_done(
    db: Session,
    folder: UserFolder,
    *,
    auto_commit: bool = True,
) -> UserFolder:
    """Complete folder processing, preserving a recorded failure."""
    folder.status = "done" if not folder.error_message else "failed"
    folder.completed_at = datetime.now(timezone.utc)
    folder.updated_at = datetime.now(timezone.utc)
    return commit_and_refresh(db, folder, auto_commit=auto_commit)


def mark_folder_failed(
    db: Session,
    folder: UserFolder,
    error_message: str,
    *,
    auto_commit: bool = True,
) -> UserFolder:
    """Mark folder processing as failed with an error message."""
    folder.status = "failed"
    folder.error_message = error_message
    folder.completed_at = datetime.now(timezone.utc)
    folder.updated_at = datetime.now(timezone.utc)
    return commit_and_refresh(db, folder, auto_commit=auto_commit)
