from __future__ import annotations

import logging
import mimetypes
from functools import lru_cache

from src.db.config import get_settings

logger = logging.getLogger(__name__)


def storage_is_configured() -> bool:
    settings = get_settings()
    return bool(
        settings.SUPABASE_URL
        and settings.SUPABASE_SERVICE_ROLE_KEY
        and settings.SUPABASE_STORAGE_BUCKET
    )


def upload_image(
    *,
    user_id,
    image_id,
    image_bytes: bytes,
    mime_type: str | None = None,
) -> str:
    settings = get_settings()
    content_type = mime_type or "image/jpeg"
    file_extension = _guess_extension(content_type)
    file_path = f"{user_id}/{image_id}{file_extension}"
    logger.info(
        "Uploading image to Supabase Storage bucket=%s path=%s",
        settings.SUPABASE_STORAGE_BUCKET,
        file_path,
    )

    _get_storage_bucket().upload(
        path=file_path,
        file=image_bytes,
        file_options={
            "content-type": content_type,
            "upsert": "true",
        },
    )
    return file_path


def download_image(file_path: str) -> bytes:
    logger.debug("Downloading image from Supabase Storage path=%s", file_path)
    return _get_storage_bucket().download(file_path)


def get_signed_url(file_path: str, expires_in: int = 3600) -> str:
    logger.debug("Creating signed URL for path=%s expires_in=%s", file_path, expires_in)
    response = _get_storage_bucket().create_signed_url(
        path=file_path,
        expires_in=expires_in,
    )
    return response["signedURL"]


def delete_image(file_path: str) -> None:
    logger.info("Deleting image from Supabase Storage path=%s", file_path)
    _get_storage_bucket().remove([file_path])


@lru_cache
def _get_supabase_client():
    settings = get_settings()
    if not storage_is_configured():
        raise RuntimeError("Supabase Storage is not configured")

    from supabase import create_client

    return create_client(
        supabase_url=_normalize_supabase_url(settings.SUPABASE_URL),
        supabase_key=settings.SUPABASE_SERVICE_ROLE_KEY,
    )


def _get_storage_bucket():
    settings = get_settings()
    return _get_supabase_client().storage.from_(settings.SUPABASE_STORAGE_BUCKET)


def _normalize_supabase_url(url: str) -> str:
    trimmed = url.strip().rstrip("/")
    if ".storage.supabase.co" not in trimmed:
        return trimmed

    without_protocol = trimmed.split("://", 1)[-1]
    host = without_protocol.split("/", 1)[0]
    project_ref = host.split(".storage.supabase.co", 1)[0]
    scheme = trimmed.split("://", 1)[0] if "://" in trimmed else "https"
    return f"{scheme}://{project_ref}.supabase.co"


def _guess_extension(mime_type: str) -> str:
    extension = mimetypes.guess_extension(mime_type, strict=False)
    if extension == ".jpe":
        return ".jpg"
    return extension or ".bin"
