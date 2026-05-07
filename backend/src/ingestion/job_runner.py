from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from src.ingestion.retry import process_drive_files, retry_failed_files
from src.ingestion.state import record_final_failures
from src.models.ingestion_job import IngestionJob
from src.models.user_folder import UserFolder
from src.services import drive_service
from src.services.folder_service import (
    mark_folder_done,
    mark_folder_failed,
    mark_folder_processing,
    set_folder_total_images,
)
from src.services.job_service import (
    mark_job_done,
    mark_job_failed,
    mark_job_running,
    set_job_total,
)

logger = logging.getLogger(__name__)


def run_ingestion_job(db: Session, *, job_id) -> IngestionJob:
    job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
    if job is None:
        raise ValueError("Ingestion job not found")

    folder = None
    if job.folder_id:
        folder = db.query(UserFolder).filter(UserFolder.id == job.folder_id).first()
    if folder is None:
        return mark_job_failed(db, job, "Folder not found for ingestion job")

    try:
        logger.info("Starting ingestion job_id=%s user_id=%s", job.id, job.user_id)
        mark_job_running(db, job, auto_commit=False)
        mark_folder_processing(db, folder, auto_commit=False)
        db.commit()

        drive_files = drive_service.list_images_in_folder(
            folder.drive_folder_id,
            job.user_id,
            db,
        )
        set_job_total(db, job, len(drive_files), auto_commit=False)
        set_folder_total_images(db, folder, len(drive_files), auto_commit=False)
        db.commit()
        logger.info(
            "Ingestion job_id=%s discovered %s files for folder_id=%s",
            job.id,
            len(drive_files),
            folder.drive_folder_id,
        )

        initial_failures = process_drive_files(
            db,
            job=job,
            folder=folder,
            drive_files=drive_files,
            attempt_label="initial",
        )
        final_failures = retry_failed_files(
            db,
            job=job,
            folder=folder,
            failures=initial_failures,
        )
        record_final_failures(db, job=job, folder=folder, failures=final_failures)

        job = db.query(IngestionJob).filter(IngestionJob.id == job.id).first()
        folder = db.query(UserFolder).filter(UserFolder.id == folder.id).first()
        if job.failed and job.processed == 0:
            error_message = job.error_message or "All files failed during ingestion"
            mark_folder_failed(db, folder, error_message, auto_commit=False)
            mark_job_failed(db, job, error_message, auto_commit=False)
            db.commit()
            logger.warning("Ingestion job_id=%s failed for all files", job.id)
            return job

        mark_folder_done(db, folder, auto_commit=False)
        mark_job_done(db, job, auto_commit=False)
        db.commit()
        logger.info(
            "Finished ingestion job_id=%s processed=%s failed=%s",
            job.id,
            job.processed,
            job.failed,
        )
        return job
    except Exception as exc:
        db.rollback()
        logger.exception("Unhandled ingestion failure job_id=%s: %s", job.id, exc)
        if folder is not None:
            mark_folder_failed(db, folder, str(exc), auto_commit=False)
        mark_job_failed(db, job, str(exc), auto_commit=False)
        db.commit()
        return job
