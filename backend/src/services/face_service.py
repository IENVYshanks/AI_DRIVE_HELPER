"""Detect faces and coordinate their relational representation.

InsightFace produces bounding boxes and 512-value embeddings. This module
normalizes that output for the ingestion pipeline and maintains matching Face
rows in Postgres. Vector persistence itself belongs to ``vector_service``.
"""

from __future__ import annotations

import io
import threading
import warnings
from typing import TYPE_CHECKING, Any

import numpy as np
from PIL import Image as PILImage, UnidentifiedImageError
from sqlalchemy.orm import Session

from src.models.face import Face
from src.models.image import Image
from src.db.config import get_settings

if TYPE_CHECKING:
    from insightface.app import FaceAnalysis

# Model initialization is expensive, so one analyzer is shared by the process.
_FACE_ANALYZER_LOCK = threading.Lock()
_FACE_ANALYZER: FaceAnalysis | None = None
_INFERENCE_LIMIT_LOCK = threading.Lock()
_INFERENCE_SEMAPHORE: threading.BoundedSemaphore | None = None
_INFERENCE_LIMIT: int | None = None
SUPPORTED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}


class InvalidImageError(ValueError):
    """Raised when image structure or decoded dimensions violate policy."""


class FaceInferenceBusyError(RuntimeError):
    """Raised when the bounded inference queue cannot accept more work."""


def decode_image_bytes(image_bytes: bytes) -> np.ndarray:
    """Validate image structure and dimensions before allocating an RGB array."""
    settings = get_settings()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", PILImage.DecompressionBombWarning)
            with PILImage.open(io.BytesIO(image_bytes)) as image:
                image_format = (image.format or "").upper()
                width, height = image.size
                frame_count = getattr(image, "n_frames", 1)
                if image_format not in SUPPORTED_IMAGE_FORMATS:
                    raise InvalidImageError("Unsupported image format")
                if width <= 0 or height <= 0:
                    raise InvalidImageError("Image dimensions are invalid")
                if width > settings.MAX_IMAGE_WIDTH or height > settings.MAX_IMAGE_HEIGHT:
                    raise InvalidImageError("Image dimensions exceed the configured limit")
                if width * height > settings.MAX_IMAGE_PIXELS:
                    raise InvalidImageError("Image pixel count exceeds the configured limit")
                if frame_count > settings.MAX_IMAGE_FRAMES:
                    raise InvalidImageError("Multi-frame images are not supported")
                image.load()
                return np.asarray(image.convert("RGB"))
    except InvalidImageError:
        raise
    except (UnidentifiedImageError, OSError, PILImage.DecompressionBombError) as exc:
        raise InvalidImageError("Image data is invalid") from exc


def extract_faces_and_embeddings(image_bytes: bytes) -> list[dict[str, Any]]:
    """Decode an image and return normalized InsightFace detections.

    Empty output means either no face was found or the model could not analyze
    the image. Individual detections missing an embedding or box are ignored.
    """
    # Pillow decodes into RGB, while InsightFace/OpenCV expects BGR ordering.
    rgb_array = decode_image_bytes(image_bytes)
    bgr_array = rgb_array[:, :, ::-1]

    semaphore = _get_inference_semaphore()
    wait_seconds = get_settings().FACE_INFERENCE_WAIT_SECONDS
    if not semaphore.acquire(timeout=wait_seconds):
        raise FaceInferenceBusyError("Face inference capacity is busy")
    try:
        detections = _get_face_analyzer().get(bgr_array)
    except Exception:
        return []
    finally:
        semaphore.release()

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
    """Choose the strongest query face, preferring confidence then face area."""
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
    """Replace an image's Face rows with the latest detector output.

    This prevents duplicate rows when an image is re-ingested. ``flush``
    assigns IDs without committing because the caller owns the full file
    transaction and still needs those IDs for Qdrant points.
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
    """Store each face's corresponding Qdrant point ID in Postgres."""
    if not face_point_ids:
        return

    for face_id, point_id in face_point_ids.items():
        (
            db.query(Face)
            .filter(Face.id == face_id)
            .update({"qdrant_point_id": point_id}, synchronize_session=False)
        )


def _to_float(value: Any) -> float | None:
    """Convert optional model scalars, including NumPy values, to Python floats."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _get_face_analyzer() -> FaceAnalysis:
    """Lazily initialize the process-wide CPU InsightFace model once."""
    global _FACE_ANALYZER

    if _FACE_ANALYZER is None:
        # Double-checked locking avoids serializing every later inference call
        # while preventing concurrent requests from loading the model twice.
        with _FACE_ANALYZER_LOCK:
            if _FACE_ANALYZER is None:
                # Importing InsightFace also imports its model stack, so defer it
                # until the first inference rather than slowing API startup.
                from insightface.app import FaceAnalysis

                analyzer = FaceAnalysis(
                    name="buffalo_l",
                    providers=["CPUExecutionProvider"],
                )
                analyzer.prepare(ctx_id=-1)
                _FACE_ANALYZER = analyzer

    return _FACE_ANALYZER


def _get_inference_semaphore() -> threading.BoundedSemaphore:
    """Return a process-wide semaphore sized from validated configuration."""
    global _INFERENCE_SEMAPHORE, _INFERENCE_LIMIT
    limit = get_settings().MAX_CONCURRENT_FACE_INFERENCES
    if _INFERENCE_SEMAPHORE is None or _INFERENCE_LIMIT != limit:
        with _INFERENCE_LIMIT_LOCK:
            if _INFERENCE_SEMAPHORE is None or _INFERENCE_LIMIT != limit:
                _INFERENCE_SEMAPHORE = threading.BoundedSemaphore(limit)
                _INFERENCE_LIMIT = limit
    return _INFERENCE_SEMAPHORE
