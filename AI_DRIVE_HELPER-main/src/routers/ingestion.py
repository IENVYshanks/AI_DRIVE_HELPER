from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from src.db.database import SessionLocal, get_db
from src.dependencies import get_current_user
from src.models.image import Image
from src.models.ingestion_job import IngestionJob
from src.models.user_folder import UserFolder
from src.models.users import User
from src.services.ingestion_service import (
    create_or_update_folder,
    get_all_images_for_user,
    get_folder_for_user,
    get_job_for_user,
    run_ingestion_job,
    start_ingestion_job,
)
from src.services.storage_service import get_signed_url, storage_is_configured

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


class UpsertFolderRequest(BaseModel):
    drive_folder_id: str
    folder_name: str | None = None


class StartIngestionRequest(BaseModel):
    job_type: str = "full"


class FolderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    drive_folder_id: str
    folder_name: str | None
    status: str
    total_images: int
    processed_images: int
    failed_images: int
    error_message: str | None


class IngestionJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    folder_id: UUID | None
    status: str
    job_type: str
    total: int
    processed: int
    failed: int
    error_message: str | None
    failed_file_ids: list[str] | None


class IngestedImageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    folder_id: UUID | None
    drive_file_id: str
    drive_file_name: str | None
    mime_type: str | None
    file_size_bytes: int | None
    status: str
    face_count: int
    error_message: str | None
    image_url: str | None = None


@router.post("/folders", response_model=FolderResponse, status_code=status.HTTP_201_CREATED)
async def upsert_folder(
    payload: UpsertFolderRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserFolder:
    if not payload.drive_folder_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="drive_folder_id is required",
        )

    return await run_in_threadpool(
        create_or_update_folder,
        db,
        user_id=current_user.id,
        drive_folder_id=payload.drive_folder_id,
        folder_name=payload.folder_name,
    )


@router.post(
    "/folders/{folder_id}/start",
    response_model=IngestionJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_folder_ingestion(
    folder_id: UUID,
    payload: StartIngestionRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IngestionJob:
    folder = await run_in_threadpool(
        get_folder_for_user,
        db,
        folder_id=folder_id,
        user_id=current_user.id,
    )
    if folder is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found",
        )

    job = await run_in_threadpool(
        start_ingestion_job,
        db,
        user_id=current_user.id,
        folder_id=folder.id,
        job_type=payload.job_type,
    )
    background_tasks.add_task(_run_ingestion_job_in_new_session, job.id)
    return job


@router.get("/folders/{folder_id}", response_model=FolderResponse)
async def get_folder_status(
    folder_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserFolder:
    folder = await run_in_threadpool(
        get_folder_for_user,
        db,
        folder_id=folder_id,
        user_id=current_user.id,
    )
    if folder is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found",
        )
    return folder


@router.get("/jobs/{job_id}", response_model=IngestionJobResponse)
async def get_job_status(
    job_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IngestionJob:
    job = await run_in_threadpool(
        get_job_for_user,
        db,
        job_id=job_id,
        user_id=current_user.id,
    )
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ingestion job not found",
        )
    return job


@router.get("/images", response_model=list[IngestedImageResponse])
async def get_all_ingested_images(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Image]:
    images = await run_in_threadpool(
        get_all_images_for_user,
        db,
        user_id=current_user.id,
    )
    return [_to_ingested_image_response(image) for image in images]


def _to_ingested_image_response(image: Image) -> IngestedImageResponse:
    image_url = None
    if storage_is_configured() and image.storage_key:
        image_url = get_signed_url(image.storage_key)

    return IngestedImageResponse(
        id=image.id,
        folder_id=image.folder_id,
        drive_file_id=image.drive_file_id,
        drive_file_name=image.drive_file_name,
        mime_type=image.mime_type,
        file_size_bytes=image.file_size_bytes,
        status=image.status,
        face_count=image.face_count or 0,
        error_message=image.error_message,
        image_url=image_url,
    )


def _run_ingestion_job_in_new_session(job_id: UUID) -> None:
    db = SessionLocal()
    try:
        run_ingestion_job(db, job_id=job_id)
    finally:
        db.close()
