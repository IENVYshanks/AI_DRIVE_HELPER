from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.dependencies import get_current_user
from src.models.users import User
from src.services.search_service import get_search_query_for_user, run_face_search
from src.services.storage_service import get_signed_url, storage_is_configured

router = APIRouter(prefix="/search", tags=["search"])


class SearchResultItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    image_id: UUID
    face_id: UUID | None
    similarity_score: float | None
    rank: int | None
    image_name: str | None
    drive_file_id: str | None
    image_url: str | None = None


class SearchQueryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    face_detected: bool
    results_count: int
    top_score: float | None
    search_latency_ms: int | None
    results: list[SearchResultItemResponse]


@router.post("", response_model=SearchQueryResponse, status_code=status.HTTP_201_CREATED)
async def search_faces(
    image: UploadFile = File(...),
    limit: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SearchQueryResponse:
    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded image is empty",
        )

    search_query = await run_in_threadpool(
        run_face_search,
        db,
        user_id=current_user.id,
        image_bytes=image_bytes,
        query_image_storage_key=image.filename,
        limit=limit,
    )
    hydrated = await run_in_threadpool(
        get_search_query_for_user,
        db,
        query_id=search_query.id,
        user_id=current_user.id,
    )
    if hydrated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Search query not found after execution",
        )

    return _to_response(hydrated)


@router.get("/{query_id}", response_model=SearchQueryResponse)
async def get_search_query(
    query_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SearchQueryResponse:
    search_query = await run_in_threadpool(
        get_search_query_for_user,
        db,
        query_id=query_id,
        user_id=current_user.id,
    )
    if search_query is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Search query not found",
        )

    return _to_response(search_query)


def _to_response(search_query) -> SearchQueryResponse:
    ordered_results = sorted(search_query.results, key=lambda result: result.rank or 0)
    return SearchQueryResponse(
        id=search_query.id,
        face_detected=search_query.face_detected,
        results_count=search_query.results_count,
        top_score=search_query.top_score,
        search_latency_ms=search_query.search_latency_ms,
        results=[
            SearchResultItemResponse(
                id=result.id,
                image_id=result.image_id,
                face_id=result.face_id,
                similarity_score=result.similarity_score,
                rank=result.rank,
                image_name=result.image.drive_file_name if result.image else None,
                drive_file_id=result.image.drive_file_id if result.image else None,
                image_url=(
                    get_signed_url(result.image.storage_key)
                    if result.image and result.image.storage_key and storage_is_configured()
                    else None
                ),
            )
            for result in ordered_results
        ],
    )
