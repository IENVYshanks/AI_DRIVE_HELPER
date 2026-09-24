"""Google Drive access used by folder registration and image ingestion.

Tokens are stored on the User row after authentication. This service turns
those tokens into a Drive client, lists direct image children, and downloads
their bytes for the ingestion pipeline.
"""

from __future__ import annotations

import logging
import io
from datetime import timezone
from typing import Any, TypedDict

from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
from sqlalchemy.orm import Session

from src.db.config import get_settings
from src.models.users import User
from src.services.oauth_token_cipher import (
    decrypt_oauth_token,
    encrypt_oauth_token,
    oauth_token_needs_rotation,
)

logger = logging.getLogger(__name__)
FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"


class DriveDownloadLimitExceeded(ValueError):
    """Raised before a Drive response can exceed the configured memory budget."""


class DriveFolderMetadata(TypedDict):
    """Safe folder metadata returned to the authenticated frontend."""

    id: str
    name: str
    parent_id: str | None


class _LimitedBytesIO(io.BytesIO):
    def __init__(self, max_bytes: int):
        super().__init__()
        self.max_bytes = max_bytes

    def write(self, data: bytes) -> int:
        projected_size = max(len(self.getbuffer()), self.tell() + len(data))
        if projected_size > self.max_bytes:
            raise DriveDownloadLimitExceeded(
                f"Drive image exceeds the {self.max_bytes}-byte ingestion limit"
            )
        return super().write(data)


def get_drive_service(user_id, db: Session):
    """Build a Drive client from a user's stored OAuth credentials."""
    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.drive_access_token:
        logger.warning("No Google Drive token found for user_id=%s", user_id)
        raise ValueError("No Google Drive access token found for user")

    settings = get_settings()
    expiry = user.token_expires_at
    if expiry is not None and expiry.tzinfo is not None:
        expiry = expiry.astimezone(timezone.utc).replace(tzinfo=None)

    access_token = decrypt_oauth_token(user.drive_access_token, settings)
    refresh_token = (
        decrypt_oauth_token(user.drive_refresh_token, settings)
        if user.drive_refresh_token
        else None
    )
    credentials_changed = False
    if oauth_token_needs_rotation(user.drive_access_token, settings):
        user.drive_access_token = encrypt_oauth_token(access_token, settings)
        credentials_changed = True
    if user.drive_refresh_token and oauth_token_needs_rotation(
        user.drive_refresh_token,
        settings,
    ):
        user.drive_refresh_token = encrypt_oauth_token(refresh_token, settings)
        credentials_changed = True

    credentials = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        expiry=expiry,
    )
    if credentials.expired:
        if not credentials.refresh_token or not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
            raise ValueError("Google Drive authorization has expired; sign in again")
        credentials.refresh(GoogleAuthRequest())
        user.drive_access_token = encrypt_oauth_token(credentials.token, settings)
        if credentials.refresh_token:
            user.drive_refresh_token = encrypt_oauth_token(
                credentials.refresh_token,
                settings,
            )
        if credentials.expiry is not None:
            refreshed_expiry = credentials.expiry
            if refreshed_expiry.tzinfo is None:
                refreshed_expiry = refreshed_expiry.replace(tzinfo=timezone.utc)
            user.token_expires_at = refreshed_expiry
        credentials_changed = True
    if credentials_changed:
        db.commit()
    return build("drive", "v3", credentials=credentials)


def list_images_in_folder(folder_id: str, user_id, db: Session) -> list[dict[str, Any]]:
    """List direct image children with metadata required for ingestion.

    Drive paginates large folders. Only requested metadata is returned to keep
    responses small, and non-image children are deliberately excluded.
    """
    service = get_drive_service(user_id, db)
    files: list[dict[str, Any]] = []
    raw_item_count = 0
    sample_items: list[str] = []
    page_token = None
    settings = get_settings()
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
            if raw_item_count > settings.MAX_DRIVE_FOLDER_ITEMS:
                raise ValueError("Drive folder contains too many items")
            mime_type = item.get("mimeType", "")
            # A bounded sample makes Drive filtering problems diagnosable
            # without placing an entire large folder in the logs.
            if len(sample_items) < 20:
                sample_items.append(
                    f"{item.get('name', '<unnamed>')} [{mime_type or 'unknown'}]"
                )
            if mime_type.startswith("image/"):
                files.append(item)
                if len(files) > settings.MAX_INGESTION_FILES_PER_JOB:
                    raise ValueError("Drive folder contains too many images for one job")
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
    """Fetch the identifying metadata for a Drive folder."""
    service = get_drive_service(user_id, db)
    return (
        service.files()
        .get(fileId=folder_id, fields="id, name, mimeType, parents")
        .execute()
    )


def list_child_folders(
    parent_id: str,
    user_id,
    db: Session,
) -> list[DriveFolderMetadata]:
    """List direct child folders without exposing Google credentials."""
    service = get_drive_service(user_id, db)
    folders: list[DriveFolderMetadata] = []
    page_token = None
    settings = get_settings()
    while True:
        response = (
            service.files()
            .list(
                q=(
                    f"'{parent_id}' in parents and trashed=false and "
                    f"mimeType='{FOLDER_MIME_TYPE}'"
                ),
                spaces="drive",
                fields="nextPageToken, files(id, name, mimeType, parents)",
                orderBy="name_natural",
                pageSize=1000,
                pageToken=page_token,
                includeItemsFromAllDrives=True,
                supportsAllDrives=True,
            )
            .execute()
        )
        for item in response.get("files", []):
            if item.get("mimeType") != FOLDER_MIME_TYPE:
                continue
            folders.append(
                {
                    "id": item["id"],
                    "name": item.get("name") or "Untitled folder",
                    "parent_id": next(iter(item.get("parents", [])), None),
                }
            )
            if len(folders) > settings.MAX_DRIVE_FOLDER_ITEMS:
                raise ValueError("Google Drive contains too many folders to browse")
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return folders


def download_file_bytes(file_id: str, user_id, db: Session) -> bytes:
    """Stream a Drive file into a buffer that cannot exceed the byte limit."""
    service = get_drive_service(user_id, db)
    max_bytes = get_settings().MAX_INGESTION_IMAGE_BYTES
    logger.debug("Downloading Drive file_id=%s for user_id=%s", file_id, user_id)
    request = service.files().get_media(fileId=file_id)
    buffer = _LimitedBytesIO(max_bytes)
    downloader = MediaIoBaseDownload(
        buffer,
        request,
        chunksize=min(1024 * 1024, max_bytes),
    )
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buffer.getvalue()


def is_drive_access_error(exc: Exception) -> bool:
    """Identify Drive/auth failures that callers may present as user errors."""
    return isinstance(exc, (HttpError, ValueError))
