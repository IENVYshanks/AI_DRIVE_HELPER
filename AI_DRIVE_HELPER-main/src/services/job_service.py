from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.models.ingestion_job import IngestionJob


def create_ingestion_job(
    db: Session,
    *,
    user_id,
    folder_id,
    job_type: str = "full",
) -> IngestionJob:
    job = IngestionJob(user_id=user_id, folder_id=folder_id, job_type=job_type)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def mark_job_running(
    db: Session,
    job: IngestionJob,
    *,
    auto_commit: bool = True,
) -> IngestionJob:
    job.status = "running"
    job.started_at = job.started_at or datetime.now(timezone.utc)
    job.completed_at = None
    job.error_message = None
    job.updated_at = datetime.now(timezone.utc)
    if auto_commit:
        db.commit()
        db.refresh(job)
    return job


def set_job_total(
    db: Session,
    job: IngestionJob,
    total: int,
    *,
    auto_commit: bool = True,
) -> IngestionJob:
    job.total = total
    job.updated_at = datetime.now(timezone.utc)
    if auto_commit:
        db.commit()
        db.refresh(job)
    return job


def increment_job_processed(
    db: Session,
    job: IngestionJob,
    count: int = 1,
    *,
    auto_commit: bool = True,
) -> IngestionJob:
    job.processed = (job.processed or 0) + count
    job.updated_at = datetime.now(timezone.utc)
    if auto_commit:
        db.commit()
        db.refresh(job)
    return job


def increment_job_failed(
    db: Session,
    job: IngestionJob,
    *,
    file_id: str | None = None,
    error_message: str | None = None,
    count: int = 1,
    auto_commit: bool = True,
) -> IngestionJob:
    job.failed = (job.failed or 0) + count
    failed_ids = list(job.failed_file_ids or [])
    if file_id:
        failed_ids.append(file_id)
    job.failed_file_ids = failed_ids or None
    if error_message:
        job.error_message = error_message
    job.updated_at = datetime.now(timezone.utc)
    if auto_commit:
        db.commit()
        db.refresh(job)
    return job


def mark_job_done(
    db: Session,
    job: IngestionJob,
    *,
    auto_commit: bool = True,
) -> IngestionJob:
    job.status = "done" if not job.error_message else "failed"
    job.completed_at = datetime.now(timezone.utc)
    job.updated_at = datetime.now(timezone.utc)
    if auto_commit:
        db.commit()
        db.refresh(job)
    return job


def mark_job_failed(
    db: Session,
    job: IngestionJob,
    error_message: str,
    *,
    auto_commit: bool = True,
) -> IngestionJob:
    job.status = "failed"
    job.error_message = error_message
    job.completed_at = datetime.now(timezone.utc)
    job.updated_at = datetime.now(timezone.utc)
    if auto_commit:
        db.commit()
        db.refresh(job)
    return job
