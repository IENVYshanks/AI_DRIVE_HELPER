from __future__ import annotations

import logging
from datetime import datetime, timezone
from time import perf_counter
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from src.models.face import Face
from src.models.image import Image
from src.models.search_query import SearchQuery
from src.models.search_result import SearchResult
from src.services.face_service import extract_primary_face_embedding
from src.services.vector_service import search_similar_faces

logger = logging.getLogger(__name__)


def create_search_query(
    db: Session,
    *,
    user_id,
    query_image_storage_key: str | None = None,
) -> SearchQuery:
    query = SearchQuery(
        user_id=user_id,
        query_image_storage_key=query_image_storage_key,
    )
    db.add(query)
    db.commit()
    db.refresh(query)
    return query


def run_face_search(
    db: Session,
    *,
    user_id,
    image_bytes: bytes,
    query_image_storage_key: str | None = None,
    limit: int = 10,
) -> SearchQuery:
    search_query = create_search_query(
        db,
        user_id=user_id,
        query_image_storage_key=query_image_storage_key,
    )

    started = perf_counter()
    logger.info("Starting face search query_id=%s user_id=%s", search_query.id, user_id)
    primary_face = extract_primary_face_embedding(image_bytes)

    if primary_face is None:
        logger.info("No face detected for search query_id=%s", search_query.id)
        search_query.face_detected = False
        search_query.results_count = 0
        search_query.top_score = None
        search_query.search_latency_ms = _elapsed_ms(started)
        search_query.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(search_query)
        return search_query

    search_query.face_detected = True
    qdrant_results = search_similar_faces(
        user_id=user_id,
        embedding=primary_face["embedding"],
        limit=limit,
    )
    persisted_results = persist_search_results(
        db,
        query=search_query,
        qdrant_results=qdrant_results,
    )

    search_query.results_count = len(persisted_results)
    search_query.top_score = persisted_results[0].similarity_score if persisted_results else None
    search_query.search_latency_ms = _elapsed_ms(started)
    search_query.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(search_query)
    logger.info(
        "Completed face search query_id=%s results_count=%s latency_ms=%s",
        search_query.id,
        search_query.results_count,
        search_query.search_latency_ms,
    )
    return search_query


def get_search_query_for_user(db: Session, *, query_id, user_id) -> SearchQuery | None:
    return (
        db.query(SearchQuery)
        .options(
            joinedload(SearchQuery.results).joinedload(SearchResult.image),
            joinedload(SearchQuery.results).joinedload(SearchResult.face),
        )
        .filter(SearchQuery.id == query_id, SearchQuery.user_id == user_id)
        .first()
    )


def persist_search_results(db: Session, *, query: SearchQuery, qdrant_results) -> list[SearchResult]:
    db.query(SearchResult).filter(SearchResult.query_id == query.id).delete(
        synchronize_session=False
    )
    db.flush()

    face_ids: list[UUID] = []
    ordered_face_ids: list[UUID] = []
    for hit in qdrant_results:
        payload = hit.payload or {}
        face_id_value = payload.get("face_id")
        if not face_id_value:
            continue
        try:
            face_id = UUID(str(face_id_value))
        except ValueError:
            continue
        face_ids.append(face_id)
        ordered_face_ids.append(face_id)

    if not face_ids:
        db.commit()
        logger.info("No Qdrant hits persisted for search query_id=%s", query.id)
        return []

    faces = (
        db.query(Face)
        .options(joinedload(Face.image))
        .filter(Face.id.in_(face_ids))
        .all()
    )
    face_map = {face.id: face for face in faces}

    persisted_results: list[SearchResult] = []
    rank = 1
    for hit in qdrant_results:
        payload = hit.payload or {}
        face_id_value = payload.get("face_id")
        if not face_id_value:
            continue
        try:
            face_id = UUID(str(face_id_value))
        except ValueError:
            continue

        face = face_map.get(face_id)
        if face is None or face.image is None:
            continue

        result = SearchResult(
            query_id=query.id,
            image_id=face.image.id,
            face_id=face.id,
            similarity_score=float(hit.score) if hit.score is not None else None,
            rank=rank,
        )
        db.add(result)
        persisted_results.append(result)
        rank += 1

    db.commit()
    for result in persisted_results:
        db.refresh(result)
    logger.info(
        "Persisted %s search results for query_id=%s",
        len(persisted_results),
        query.id,
    )
    return persisted_results


def _elapsed_ms(started: float) -> int:
    return int((perf_counter() - started) * 1000)
