from __future__ import annotations

import io
import threading
from typing import Any

import numpy as np
from insightface.app import FaceAnalysis
from PIL import Image as PILImage
from sqlalchemy.orm import Session

from src.models.face import Face
from src.models.image import Image

_FACE_ANALYZER: FaceAnalysis | None = None
_FACE_ANALYZER_LOCK = threading.Lock()


def extract_faces_and_embeddings(image_bytes: bytes) -> list[dict[str, Any]]:
    """
    Detect faces and compute embeddings using InsightFace.
    """
    rgb_array = np.array(PILImage.open(io.BytesIO(image_bytes)).convert("RGB"))
    bgr_array = rgb_array[:, :, ::-1]

    try:
        detections = _get_face_analyzer().get(bgr_array)
    except Exception:
        return []

    results: list[dict[str, Any]] = []
    for index, detection in enumerate(detections):
        embedding = getattr(detection, "embedding", None)
        if embedding is None:
            continue

        bbox = getattr(detection, "bbox", None)
        if bbox is None or len(bbox) != 4:
            continue

        det_score = getattr(detection, "det_score", None)
        results.append(
            {
                "person_idx": index,
                "bbox_x": _to_float(bbox[0]),
                "bbox_y": _to_float(bbox[1]),
                "bbox_w": _to_float(bbox[2] - bbox[0]),
                "bbox_h": _to_float(bbox[3] - bbox[1]),
                "detection_score": _to_float(det_score),
                "embedding": embedding.tolist() if hasattr(embedding, "tolist") else embedding,
            }
        )

    return results


def extract_primary_face_embedding(image_bytes: bytes) -> dict[str, Any] | None:
    faces = extract_faces_and_embeddings(image_bytes)
    if not faces:
        return None

    return max(
        faces,
        key=lambda face: (
            face.get("detection_score") is not None,
            face.get("detection_score") or 0.0,
            (face.get("bbox_w") or 0.0) * (face.get("bbox_h") or 0.0),
        ),
    )


def replace_image_faces(
    db: Session,
    *,
    user_id,
    image: Image,
    faces: list[dict[str, Any]],
) -> list[Face]:
    """
    Replace any previously detected faces for this image.
    """
    db.query(Face).filter(Face.image_id == image.id).delete(synchronize_session=False)
    db.flush()

    created_faces: list[Face] = []
    for face in faces:
        face_row = Face(
            user_id=user_id,
            image_id=image.id,
            person_idx=face["person_idx"],
            bbox_x=face.get("bbox_x"),
            bbox_y=face.get("bbox_y"),
            bbox_w=face.get("bbox_w"),
            bbox_h=face.get("bbox_h"),
            detection_score=face.get("detection_score"),
        )
        db.add(face_row)
        created_faces.append(face_row)

    db.flush()
    return created_faces


def assign_qdrant_point_ids(
    db: Session,
    *,
    face_point_ids: dict[str, str],
) -> None:
    if not face_point_ids:
        return

    for face_id, point_id in face_point_ids.items():
        (
            db.query(Face)
            .filter(Face.id == face_id)
            .update({"qdrant_point_id": point_id}, synchronize_session=False)
        )


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _get_face_analyzer() -> FaceAnalysis:
    global _FACE_ANALYZER

    if _FACE_ANALYZER is None:
        with _FACE_ANALYZER_LOCK:
            if _FACE_ANALYZER is None:
                analyzer = FaceAnalysis(
                    name="buffalo_l",
                    providers=["CPUExecutionProvider"],
                )
                analyzer.prepare(ctx_id=-1)
                _FACE_ANALYZER = analyzer

    return _FACE_ANALYZER
