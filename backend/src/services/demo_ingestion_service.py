"""Idempotent ingestion for the fixed, local public-demo collection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

import numpy as np
from sqlalchemy.orm import Session

from src.db.config import get_settings
from src.models.image import Image
from src.models.user_folder import UserFolder
from src.models.users import User
from src.services.face_service import (
    assign_qdrant_point_ids,
    decode_image_bytes,
    extract_faces_and_embeddings,
    replace_image_faces,
)
from src.services.storage_service import storage_is_configured, upload_image
from src.services.vector_service import upsert_face_embeddings

DEMO_FOLDER_SOURCE_ID = "demo-assets-v1"
SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


@dataclass(frozen=True)
class DemoAssetAnalysis:
    path: Path
    source_id: str
    width: int
    height: int
    image_bytes: bytes
    faces: list[dict[str, Any]]


@dataclass(frozen=True)
class DemoIngestionResult:
    user_id: str
    folder_id: str
    images_processed: int
    images_skipped: int
    faces_processed: int


def analyze_demo_assets(asset_dir: Path) -> list[DemoAssetAnalysis]:
    """Validate and analyze every supported image in a deterministic order."""
    paths = sorted(
        path
        for path in asset_dir.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
    )
    if not paths:
        raise ValueError(f"No supported demo images found in {asset_dir}")

    analyses: list[DemoAssetAnalysis] = []
    for path in paths:
        image_bytes = path.read_bytes()
        decoded = decode_image_bytes(image_bytes)
        height, width = decoded.shape[:2]
        digest = sha256(image_bytes).hexdigest()
        analyses.append(
            DemoAssetAnalysis(
                path=path,
                source_id=f"demo:{digest}",
                width=width,
                height=height,
                image_bytes=image_bytes,
                faces=extract_faces_and_embeddings(image_bytes),
            )
        )
    return analyses


def ingest_demo_assets(
    db: Session,
    *,
    analyses: list[DemoAssetAnalysis],
    user_email: str,
    upload_originals: bool = True,
) -> DemoIngestionResult:
    """Persist analyzed demo assets to Postgres, Qdrant, and optional storage."""
    if not analyses:
        raise ValueError("At least one analyzed demo image is required")

    user = db.query(User).filter(User.email == user_email).first()
    if user is None:
        user = User(email=user_email, name="FaceSeek Demo")
        db.add(user)
        db.flush()

    folder = (
        db.query(UserFolder)
        .filter(
            UserFolder.user_id == user.id,
            UserFolder.drive_folder_id == DEMO_FOLDER_SOURCE_ID,
        )
        .first()
    )
    if folder is None:
        folder = UserFolder(
            user_id=user.id,
            drive_folder_id=DEMO_FOLDER_SOURCE_ID,
            folder_name="Public demo collection",
        )
        db.add(folder)
        db.flush()

    folder.status = "processing"
    folder.total_images = len(analyses)
    folder.processed_images = 0
    folder.failed_images = 0
    folder.error_message = None
    folder.started_at = datetime.now(timezone.utc)
    folder.completed_at = None
    db.commit()

    processed = 0
    skipped = 0
    face_total = 0

    try:
        for analysis in analyses:
            image = (
                db.query(Image)
                .filter(
                    Image.user_id == user.id,
                    Image.drive_file_id == analysis.source_id,
                )
                .first()
            )
            if image is not None and image.status == "done":
                skipped += 1
                face_total += image.face_count or 0
                continue

            if image is None:
                image = Image(user_id=user.id, drive_file_id=analysis.source_id)
                db.add(image)

            image.folder_id = folder.id
            image.drive_file_name = analysis.path.name
            image.file_size_bytes = len(analysis.image_bytes)
            image.mime_type = _mime_type_for_path(analysis.path)
            image.width = analysis.width
            image.height = analysis.height
            image.status = "processing"
            image.error_message = None
            db.flush()

            if upload_originals and storage_is_configured():
                image.storage_key = upload_image(
                    user_id=user.id,
                    image_id=image.id,
                    image_bytes=analysis.image_bytes,
                    mime_type=image.mime_type,
                )
                image.storage_bucket = get_settings().SUPABASE_STORAGE_BUCKET

            face_rows = replace_image_faces(
                db,
                user_id=user.id,
                image=image,
                faces=analysis.faces,
            )
            point_ids = upsert_face_embeddings(
                faces=[
                    {
                        "face_id": face_row.id,
                        "user_id": user.id,
                        "image_id": image.id,
                        "cluster_id": face_row.cluster_id,
                        "embedding": payload["embedding"],
                    }
                    for face_row, payload in zip(face_rows, analysis.faces)
                ]
            )
            assign_qdrant_point_ids(db, face_point_ids=point_ids)

            image.status = "done"
            image.face_count = len(face_rows)
            image.processed_at = datetime.now(timezone.utc)
            image.updated_at = datetime.now(timezone.utc)
            db.commit()
            processed += 1
            face_total += len(face_rows)
    except Exception:
        db.rollback()
        failed_folder = db.get(UserFolder, folder.id)
        if failed_folder is not None:
            failed_folder.status = "failed"
            failed_folder.error_message = "Demo ingestion failed"
            failed_folder.completed_at = datetime.now(timezone.utc)
            failed_folder.updated_at = datetime.now(timezone.utc)
            db.commit()
        raise

    folder = db.get(UserFolder, folder.id)
    folder.status = "done"
    folder.processed_images = len(analyses)
    folder.failed_images = 0
    folder.error_message = None
    folder.completed_at = datetime.now(timezone.utc)
    folder.updated_at = datetime.now(timezone.utc)
    db.commit()

    return DemoIngestionResult(
        user_id=str(user.id),
        folder_id=str(folder.id),
        images_processed=processed,
        images_skipped=skipped,
        faces_processed=face_total,
    )


def build_demo_manifest(
    analyses: list[DemoAssetAnalysis],
    *,
    public_prefix: str = "/demo/photos",
    matches_per_face: int = 10,
) -> dict[str, Any]:
    """Create the browser-safe manifest without exposing face embeddings."""
    photos: list[dict[str, Any]] = []
    faces: list[dict[str, Any]] = []
    matches: list[dict[str, Any]] = []

    visible_faces = {
        analysis.source_id: _visible_faces(analysis) for analysis in analyses
    }

    for photo_index, analysis in enumerate(analyses):
        photo_id = _photo_id(analysis)
        photos.append(
            {
                "id": photo_id,
                "src": f"{public_prefix.rstrip('/')}/{analysis.path.name}",
                "alt": f"Demo group photo {photo_index + 1:02d}",
            }
        )
        for face_index, face in visible_faces[analysis.source_id]:
            faces.append(
                {
                    "id": _face_id(analysis, face_index),
                    "photoId": photo_id,
                    "label": f"Person {face_index + 1}",
                    "bounds": {
                        "x": _percent(face["bbox_x"], analysis.width),
                        "y": _percent(face["bbox_y"], analysis.height),
                        "width": _percent(face["bbox_w"], analysis.width),
                        "height": _percent(face["bbox_h"], analysis.height),
                    },
                }
            )

    for source_index, source in enumerate(analyses):
        for face_index, face in visible_faces[source.source_id]:
            query_embedding = np.asarray(face["embedding"], dtype=np.float32)
            photo_scores: list[tuple[str, float]] = []
            for candidate_index, candidate in enumerate(analyses):
                candidate_faces = visible_faces[candidate.source_id]
                if candidate_index == source_index or not candidate_faces:
                    continue
                best_similarity = max(
                    _cosine_similarity(query_embedding, other["embedding"])
                    for _, other in candidate_faces
                )
                display_score = max(0.0, min(1.0, (best_similarity + 1.0) / 2.0))
                photo_scores.append((_photo_id(candidate), display_score))

            for photo_id, score in sorted(
                photo_scores, key=lambda item: item[1], reverse=True
            )[:matches_per_face]:
                matches.append(
                    {
                        "faceId": _face_id(source, face_index),
                        "photoId": photo_id,
                        "score": round(score, 4),
                    }
                )

    return {"photos": photos, "faces": faces, "matches": matches}


def _photo_id(analysis: DemoAssetAnalysis) -> str:
    return analysis.source_id.removeprefix("demo:")[:16]


def _visible_faces(
    analysis: DemoAssetAnalysis, *, limit: int = 12
) -> list[tuple[int, dict[str, Any]]]:
    """Keep the largest faces so crowded backgrounds do not overwhelm the UI."""
    indexed_faces = list(enumerate(analysis.faces))
    return sorted(
        indexed_faces,
        key=lambda item: (
            float(item[1].get("bbox_w") or 0) * float(item[1].get("bbox_h") or 0),
            float(item[1].get("detection_score") or 0),
        ),
        reverse=True,
    )[:limit]


def _face_id(analysis: DemoAssetAnalysis, face_index: int) -> str:
    return f"{_photo_id(analysis)}-face-{face_index}"


def _percent(value: Any, dimension: int) -> float:
    return round(max(0.0, min(100.0, float(value) / dimension * 100.0)), 3)


def _cosine_similarity(left: np.ndarray, right: Any) -> float:
    right_array = np.asarray(right, dtype=np.float32)
    denominator = float(np.linalg.norm(left) * np.linalg.norm(right_array))
    if denominator == 0:
        return 0.0
    return float(np.dot(left, right_array) / denominator)


def _mime_type_for_path(path: Path) -> str:
    return {
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(path.suffix.lower(), "image/jpeg")
