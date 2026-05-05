from __future__ import annotations

import logging
from typing import Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session

from src.models.users import User

logger = logging.getLogger(__name__)
FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"


def get_drive_service(user_id, db: Session):
    """
    Build a Google Drive API client from the user's stored access token.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.drive_access_token:
        logger.warning("No Google Drive token found for user_id=%s", user_id)
        raise ValueError("No Google Drive access token found for user")

    credentials = Credentials(
        token=user.drive_access_token,
        refresh_token=user.drive_refresh_token,
    )
    return build("drive", "v3", credentials=credentials)


def list_images_in_folder(folder_id: str, user_id, db: Session) -> list[dict[str, Any]]:
    """
    List images in a Google Drive folder with enough metadata for ingestion.
    Only image files directly inside the selected folder are included.
    """
    service = get_drive_service(user_id, db)
    files: list[dict[str, Any]] = []
    raw_item_count = 0
    sample_items: list[str] = []
    page_token = None
    while True:
        response = (
            service.files()
            .list(
                q=f"'{folder_id}' in parents and trashed=false",
                spaces="drive",
                fields=(
                    "nextPageToken, "
                    "files(id, name, mimeType, size, imageMediaMetadata(width,height,time))"
                ),
                pageSize=1000,
                pageToken=page_token,
                includeItemsFromAllDrives=True,
                supportsAllDrives=True,
            )
            .execute()
        )
        batch = response.get("files", [])
        for item in batch:
            raw_item_count += 1
            mime_type = item.get("mimeType", "")
            if len(sample_items) < 20:
                sample_items.append(
                    f"{item.get('name', '<unnamed>')} [{mime_type or 'unknown'}]"
                )
            if mime_type.startswith("image/"):
                files.append(item)

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    logger.info(
        "Listed %s direct Drive image files for user_id=%s folder_id=%s raw_items_seen=%s sample_items=%s",
        len(files),
        user_id,
        folder_id,
        raw_item_count,
        sample_items,
    )
    return files


def get_folder_metadata(folder_id: str, user_id, db: Session) -> dict[str, Any]:
    service = get_drive_service(user_id, db)
    return (
        service.files()
        .get(fileId=folder_id, fields="id, name, mimeType")
        .execute()
    )


def download_file_bytes(file_id: str, user_id, db: Session) -> bytes:
    service = get_drive_service(user_id, db)
    logger.debug("Downloading Drive file_id=%s for user_id=%s", file_id, user_id)
    return service.files().get_media(fileId=file_id).execute()


def is_drive_access_error(exc: Exception) -> bool:
    return isinstance(exc, (HttpError, ValueError))
