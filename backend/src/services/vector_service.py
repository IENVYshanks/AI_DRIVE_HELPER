"""Qdrant persistence and similarity search for face embeddings.

Postgres owns face metadata; Qdrant owns the vectors used for fast nearest-
neighbor search. Their shared face ID links results back to relational data.
Every search is filtered by user ID to prevent cross-user matches.
"""

from __future__ import annotations

import logging
from typing import Iterable

from qdrant_client import QdrantClient
from qdrant_client.http import models

from src.db.config import get_settings

_QDRANT_CLIENT: QdrantClient | None = None
logger = logging.getLogger(__name__)
_PAYLOAD_INDEXES: tuple[str, ...] = (
    "user_id",
    "face_id",
    "image_id",
    "cluster_id",
)


def get_qdrant_client() -> QdrantClient:
    """Lazily create and reuse the process-wide Qdrant client."""
    global _QDRANT_CLIENT

    if _QDRANT_CLIENT is None:
        settings = get_settings()
        _QDRANT_CLIENT = QdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY,
        )
        logger.info("Initialized Qdrant client for %s", settings.QDRANT_URL)

    return _QDRANT_CLIENT


def ensure_face_collection(vector_size: int) -> None:
    """Create the face collection or verify its vector dimensions.

    Embedding models have a fixed output size. Refusing a mismatch avoids
    silently writing vectors from an incompatible model into existing data.
    """
    settings = get_settings()
    client = get_qdrant_client()
    collections = client.get_collections().collections
    collection_names = {collection.name for collection in collections}

    if settings.QDRANT_COLLECTION_NAME in collection_names:
        collection_info = client.get_collection(settings.QDRANT_COLLECTION_NAME)
        vectors_config = collection_info.config.params.vectors
        existing_size = getattr(vectors_config, "size", None)
        if existing_size is not None and existing_size != vector_size:
            raise ValueError(
                "Qdrant collection vector size mismatch: "
                f"expected {existing_size}, got {vector_size}"
            )
        _ensure_payload_indexes()
        return

    logger.info(
        "Creating Qdrant collection=%s vector_size=%s",
        settings.QDRANT_COLLECTION_NAME,
        vector_size,
    )
    client.create_collection(
        collection_name=settings.QDRANT_COLLECTION_NAME,
        vectors_config=models.VectorParams(
            size=vector_size,
            distance=models.Distance.COSINE,
        ),
    )
    _ensure_payload_indexes()


def upsert_face_embedding(
    *,
    face_id,
    user_id,
    image_id,
    embedding: Iterable[float],
    cluster_id=None,
) -> str:
    """Upsert one face vector using the face ID as the Qdrant point ID."""
    embedding_list = list(embedding)
    if not embedding_list:
        raise ValueError("Embedding vector is empty")

    ensure_face_collection(len(embedding_list))
    settings = get_settings()
    client = get_qdrant_client()
    point_id = str(face_id)

    client.upsert(
        collection_name=settings.QDRANT_COLLECTION_NAME,
        points=[
            models.PointStruct(
                id=point_id,
                vector=embedding_list,
                payload={
                    "user_id": str(user_id),
                    "face_id": str(face_id),
                    "image_id": str(image_id),
                    "cluster_id": str(cluster_id) if cluster_id else None,
                },
            )
        ],
        wait=True,
    )
    return point_id


def upsert_face_embeddings(*, faces: list[dict]) -> dict[str, str]:
    """Batch-upsert detected faces and return Postgres-to-Qdrant ID mappings."""
    if not faces:
        return {}

    first_embedding = list(faces[0]["embedding"])
    if not first_embedding:
        raise ValueError("Embedding vector is empty")

    ensure_face_collection(len(first_embedding))
    settings = get_settings()
    client = get_qdrant_client()

    points = []
    point_ids: dict[str, str] = {}
    for face in faces:
        embedding_list = list(face["embedding"])
        if not embedding_list:
            raise ValueError("Embedding vector is empty")
        point_id = str(face["face_id"])
        point_ids[point_id] = point_id
        points.append(
            models.PointStruct(
                id=point_id,
                vector=embedding_list,
                payload={
                    "user_id": str(face["user_id"]),
                    "face_id": point_id,
                    "image_id": str(face["image_id"]),
                    "cluster_id": str(face["cluster_id"]) if face.get("cluster_id") else None,
                },
            )
        )

    client.upsert(
        collection_name=settings.QDRANT_COLLECTION_NAME,
        points=points,
        wait=True,
    )
    logger.info(
        "Upserted %s face embeddings into collection=%s",
        len(points),
        settings.QDRANT_COLLECTION_NAME,
    )
    return point_ids


def search_similar_faces(*, user_id, embedding: Iterable[float], limit: int = 10):
    """Return the closest face vectors belonging to one user."""
    embedding_list = list(embedding)
    if not embedding_list:
        raise ValueError("Embedding vector is empty")

    ensure_face_collection(len(embedding_list))
    settings = get_settings()
    client = get_qdrant_client()

    logger.info(
        "Searching similar faces for user_id=%s limit=%s collection=%s",
        user_id,
        limit,
        settings.QDRANT_COLLECTION_NAME,
    )
    response = client.query_points(
        collection_name=settings.QDRANT_COLLECTION_NAME,
        query=embedding_list,
        # User scoping is enforced inside Qdrant, before result limiting.
        query_filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="user_id",
                    match=models.MatchValue(value=str(user_id)),
                )
            ]
        ),
        with_payload=True,
        limit=limit,
    )
    return response.points


def _ensure_payload_indexes() -> None:
    """Ensure filterable identifiers are indexed for efficient searches."""
    settings = get_settings()
    client = get_qdrant_client()
    for field_name in _PAYLOAD_INDEXES:
        logger.debug(
            "Ensuring Qdrant payload index field=%s collection=%s",
            field_name,
            settings.QDRANT_COLLECTION_NAME,
        )
        client.create_payload_index(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            field_name=field_name,
            field_schema=models.PayloadSchemaType.KEYWORD,
        )
