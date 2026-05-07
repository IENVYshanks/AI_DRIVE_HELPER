from __future__ import annotations

import logging
from time import perf_counter

from sqlalchemy.orm import Session

from src.db.config import get_settings
from src.ingestion.results import FileProcessResult
from src.ingestion.state import (
    get_existing_image_for_drive_file,
    image_matches_drive_file,
    mark_drive_file_failed,
    upsert_image_from_drive_file,
)
from src.models.image import Image
from src.models.ingestion_job import IngestionJob
from src.models.user_folder import UserFolder
from src.services import drive_service
from src.services.face_service import (
    assign_qdrant_point_ids,
    extract_faces_and_embeddings,
    replace_image_faces,
)
from src.services.folder_service import increment_folder_processed
from src.services.image_service import (
    mark_image_done,
    mark_image_processing,
    set_image_storage_location,
)
from src.services.job_service import increment_job_processed
from src.services.storage_service import storage_is_configured, upload_image
from src.services.vector_service import upsert_face_embeddings

logger = logging.getLogger(__name__)


def process_drive_file(
    db: Session,
    *,
    job: IngestionJob,
    folder: UserFolder,
    drive_file: dict,
    attempt_label: str,
) -> FileProcessResult:
    started_at = perf_counter()
    try:
        drive_file_id = _get_drive_file_id(drive_file)
        _log_file_processing_started(job, drive_file, drive_file_id, attempt_label)

        if _should_skip_already_ingested_file(db, job, drive_file, drive_file_id):
            _mark_file_skipped(db, job, folder, drive_file_id, attempt_label)
            return FileProcessResult(drive_file=drive_file)

        image = _prepare_image_for_processing(db, job, folder, drive_file)
        image_bytes = _download_drive_file(db, job, drive_file_id)
        _store_image_if_configured(db, job, image, image_bytes)

        face_count = _extract_and_store_faces(db, job, image, image_bytes, drive_file_id)
        _mark_file_processed(
            db,
            job,
            folder,
            image,
            face_count,
            attempt_label,
            started_at,
        )
        return FileProcessResult(drive_file=drive_file)
    except Exception as exc:
        error_message = _handle_processing_failure(
            db,
            job=job,
            folder=folder,
            drive_file=drive_file,
            attempt_label=attempt_label,
            exc=exc,
        )
        return FileProcessResult(drive_file=drive_file, error_message=error_message)


def _get_drive_file_id(drive_file: dict) -> str:
    drive_file_id = drive_file.get("id")
    if not drive_file_id:
        raise ValueError("Drive file is missing required id")
    return drive_file_id


def _log_file_processing_started(
    job: IngestionJob,
    drive_file: dict,
    drive_file_id: str,
    attempt_label: str,
) -> None:
    logger.info(
        "Processing Drive file_id=%s name=%s for job_id=%s attempt=%s",
        drive_file_id,
        drive_file.get("name"),
        job.id,
        attempt_label,
    )


def _prepare_image_for_processing(
    db: Session,
    job: IngestionJob,
    folder: UserFolder,
    drive_file: dict,
) -> Image:
    image = upsert_image_from_drive_file(
        db,
        user_id=job.user_id,
        folder_id=folder.id,
        drive_file=drive_file,
        auto_commit=False,
    )
    mark_image_processing(db, image, auto_commit=False)
    return image


def _should_skip_already_ingested_file(
    db: Session,
    job: IngestionJob,
    drive_file: dict,
    drive_file_id: str,
) -> bool:
    if not get_settings().SKIP_ALREADY_INGESTED:
        return False

    image = get_existing_image_for_drive_file(
        db,
        user_id=job.user_id,
        drive_file_id=drive_file_id,
    )
    return bool(
        image
        and image.status == "done"
        and image_matches_drive_file(image, drive_file)
    )


def _mark_file_skipped(
    db: Session,
    job: IngestionJob,
    folder: UserFolder,
    drive_file_id: str,
    attempt_label: str,
) -> None:
    increment_job_processed(db, job, auto_commit=False)
    increment_folder_processed(db, folder, auto_commit=False)
    db.commit()
    logger.info(
        "Skipped already ingested drive_file_id=%s job_id=%s attempt=%s",
        drive_file_id,
        job.id,
        attempt_label,
    )


def _download_drive_file(db: Session, job: IngestionJob, drive_file_id: str) -> bytes:
    return drive_service.download_file_bytes(drive_file_id, job.user_id, db)


def _store_image_if_configured(
    db: Session,
    job: IngestionJob,
    image: Image,
    image_bytes: bytes,
) -> None:
    if not storage_is_configured():
        return

    storage_bucket = get_settings().SUPABASE_STORAGE_BUCKET or ""
    storage_key = upload_image(
        user_id=job.user_id,
        image_id=image.id,
        image_bytes=image_bytes,
        mime_type=image.mime_type,
    )
    set_image_storage_location(
        db,
        image,
        storage_key=storage_key,
        storage_bucket=storage_bucket,
        auto_commit=False,
    )
    logger.info(
        "Stored image_id=%s in bucket=%s path=%s",
        image.id,
        storage_bucket,
        storage_key,
    )


def _extract_and_store_faces(
    db: Session,
    job: IngestionJob,
    image: Image,
    image_bytes: bytes,
    drive_file_id: str,
) -> int:
    faces = extract_faces_and_embeddings(image_bytes)
    logger.info(
        "Detected %s faces for image_id=%s drive_file_id=%s",
        len(faces),
        image.id,
        drive_file_id,
    )
    face_rows = replace_image_faces(
        db,
        user_id=job.user_id,
        image=image,
        faces=faces,
    )
    point_ids = upsert_face_embeddings(
        faces=[
            {
                "face_id": face_row.id,
                "user_id": job.user_id,
                "image_id": image.id,
                "cluster_id": face_row.cluster_id,
                "embedding": face_payload["embedding"],
            }
            for face_row, face_payload in zip(face_rows, faces)
        ]
    )
    assign_qdrant_point_ids(db, face_point_ids=point_ids)
    return len(faces)


def _mark_file_processed(
    db: Session,
    job: IngestionJob,
    folder: UserFolder,
    image: Image,
    face_count: int,
    attempt_label: str,
    started_at: float,
) -> None:
    mark_image_done(db, image, face_count=face_count, auto_commit=False)
    increment_job_processed(db, job, auto_commit=False)
    increment_folder_processed(db, folder, auto_commit=False)
    db.commit()
    logger.info(
        "Completed processing image_id=%s job_id=%s attempt=%s duration_ms=%s",
        image.id,
        job.id,
        attempt_label,
        round((perf_counter() - started_at) * 1000),
    )


def _handle_processing_failure(
    db: Session,
    *,
    job: IngestionJob,
    folder: UserFolder,
    drive_file: dict,
    attempt_label: str,
    exc: Exception,
) -> str:
    db.rollback()
    error_message = str(exc)
    logger.exception(
        "Failed processing drive_file_id=%s job_id=%s attempt=%s: %s",
        drive_file.get("id"),
        job.id,
        attempt_label,
        exc,
    )
    mark_drive_file_failed(
        db,
        job=job,
        folder=folder,
        drive_file=drive_file,
        error_message=error_message,
    )
    return error_message
