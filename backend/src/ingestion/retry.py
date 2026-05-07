from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from src.ingestion.file_processor import process_drive_file
from src.ingestion.results import FileProcessResult
from src.models.ingestion_job import IngestionJob
from src.models.user_folder import UserFolder

logger = logging.getLogger(__name__)


def process_drive_files(
    db: Session,
    *,
    job: IngestionJob,
    folder: UserFolder,
    drive_files: list[dict],
    attempt_label: str,
) -> list[FileProcessResult]:
    failures = []
    for drive_file in drive_files:
        result = process_drive_file(
            db,
            job=job,
            folder=folder,
            drive_file=drive_file,
            attempt_label=attempt_label,
        )
        if result.failed:
            failures.append(result)
    return failures


def retry_failed_files(
    db: Session,
    *,
    job: IngestionJob,
    folder: UserFolder,
    failures: list[FileProcessResult],
) -> list[FileProcessResult]:
    if not failures:
        return []

    logger.info(
        "Retrying %s failed files after initial ingestion pass for job_id=%s",
        len(failures),
        job.id,
    )
    return process_drive_files(
        db,
        job=job,
        folder=folder,
        drive_files=[result.drive_file for result in failures],
        attempt_label="retry",
    )
