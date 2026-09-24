"""Create named demo identities and match them to the fixed photo library."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

import numpy as np
from sqlalchemy.orm import Session

from src.models.face import Face
from src.models.image import Image
from src.models.person_cluster import PersonCluster
from src.models.users import User
from src.services.face_service import extract_primary_face_embedding
from src.services.vector_service import (
    search_similar_faces,
    set_face_cluster_payload,
    upsert_demo_person_embedding,
)

PERSON_FILE_PREFIXES = {
    "Chris Hemsworth": ("chris",),
    "Jeremy Renner": ("jeremy", "jemery"),
    "Robert Downey Jr.": ("robertd",),
    "Scarlett Johansson": ("scarlet", "sacrlet"),
}
SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


@dataclass(frozen=True)
class DemoPersonAnalysis:
    name: str
    portrait_paths: tuple[Path, ...]
    centroid: list[float]


@dataclass(frozen=True)
class DemoPersonMatch:
    photo_name: str
    score: float


@dataclass(frozen=True)
class DemoPersonResult:
    id: str
    name: str
    portraits: tuple[str, ...]
    matches: tuple[DemoPersonMatch, ...]


def analyze_demo_people(face_dir: Path) -> list[DemoPersonAnalysis]:
    """Build one normalized centroid from every named portrait group."""
    paths = sorted(
        path
        for path in face_dir.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
    )
    analyses: list[DemoPersonAnalysis] = []
    for name, prefixes in PERSON_FILE_PREFIXES.items():
        portraits = tuple(
            path for path in paths if path.stem.lower().startswith(prefixes)
        )
        if not portraits:
            raise ValueError(f"No portraits found for {name}")

        embeddings: list[np.ndarray] = []
        for portrait in portraits:
            face = extract_primary_face_embedding(portrait.read_bytes())
            if face is None:
                raise ValueError(f"No face detected in {portrait.name}")
            embeddings.append(_normalized(face["embedding"]))

        centroid = _normalized(np.mean(embeddings, axis=0)).tolist()
        analyses.append(
            DemoPersonAnalysis(
                name=name,
                portrait_paths=portraits,
                centroid=centroid,
            )
        )
    return analyses


def ingest_demo_people(
    db: Session,
    *,
    analyses: list[DemoPersonAnalysis],
    user_email: str,
    match_limit: int = 100,
    minimum_similarity: float = 0.3,
) -> list[DemoPersonResult]:
    """Persist named centroids and attach strongest library matches to clusters."""
    user = db.query(User).filter(User.email == user_email).one()
    results: list[DemoPersonResult] = []

    for analysis in analyses:
        cluster = (
            db.query(PersonCluster)
            .filter(
                PersonCluster.user_id == user.id,
                PersonCluster.label == analysis.name,
            )
            .first()
        )
        if cluster is None:
            cluster = PersonCluster(user_id=user.id, label=analysis.name)
            db.add(cluster)
            db.flush()

        upsert_demo_person_embedding(
            person_id=cluster.id,
            user_id=user.id,
            label=analysis.name,
            embedding=analysis.centroid,
        )
        hits = search_similar_faces(
            user_id=user.id,
            embedding=analysis.centroid,
            limit=match_limit,
        )
        matched = _resolve_matches(
            db,
            user_id=user.id,
            hits=hits,
            minimum_similarity=minimum_similarity,
        )

        faces = [item["face"] for item in matched]
        for face in faces:
            face.cluster_id = cluster.id
        cluster.thumbnail_face_id = faces[0].id if faces else None
        cluster.face_count = len(faces)
        cluster.image_count = len({face.image_id for face in faces})

        set_face_cluster_payload(
            point_ids=[face.qdrant_point_id for face in faces if face.qdrant_point_id],
            cluster_id=cluster.id,
        )
        db.commit()

        results.append(
            DemoPersonResult(
                id=str(cluster.id),
                name=analysis.name,
                portraits=tuple(path.name for path in analysis.portrait_paths),
                matches=tuple(
                    DemoPersonMatch(
                        photo_name=item["face"].image.drive_file_name,
                        score=round(float(item["score"]), 4),
                    )
                    for item in matched
                    if item["face"].image.drive_file_name
                ),
            )
        )

    return results


def build_demo_people_manifest(
    results: list[DemoPersonResult],
    *,
    photos: list[dict[str, Any]],
    portrait_prefix: str = "/demo/people",
) -> list[dict[str, Any]]:
    """Map database filenames to browser photo IDs without exposing vectors."""
    photo_ids = {Path(photo["src"]).name: photo["id"] for photo in photos}
    people: list[dict[str, Any]] = []
    for result in results:
        people.append(
            {
                "id": result.id,
                "name": result.name,
                "portraits": [
                    f"{portrait_prefix.rstrip('/')}/{filename}"
                    for filename in result.portraits
                ],
                "matches": [
                    {
                        "photoId": photo_ids[match.photo_name],
                        "score": round(max(0.0, min(1.0, (match.score + 1.0) / 2.0)), 4),
                    }
                    for match in result.matches
                    if match.photo_name in photo_ids
                ],
            }
        )
    return people


def _resolve_matches(
    db: Session,
    *,
    user_id,
    hits,
    minimum_similarity: float,
) -> list[dict[str, Any]]:
    """Return the strongest valid face per image in Qdrant rank order."""
    scored_ids: list[tuple[UUID, float]] = []
    for hit in hits:
        payload = hit.payload or {}
        try:
            face_id = UUID(str(payload.get("face_id")))
        except (TypeError, ValueError):
            continue
        score = float(hit.score or 0.0)
        if score >= minimum_similarity:
            scored_ids.append((face_id, score))

    if not scored_ids:
        return []
    faces = (
        db.query(Face)
        .join(Image, Face.image_id == Image.id)
        .filter(
            Face.id.in_([face_id for face_id, _ in scored_ids]),
            Face.user_id == user_id,
            Image.user_id == user_id,
        )
        .all()
    )
    face_map = {face.id: face for face in faces}
    seen_images = set()
    resolved: list[dict[str, Any]] = []
    for face_id, score in scored_ids:
        face = face_map.get(face_id)
        if face is None or face.image_id in seen_images:
            continue
        seen_images.add(face.image_id)
        resolved.append({"face": face, "score": score})
    return resolved


def _normalized(values: Any) -> np.ndarray:
    vector = np.asarray(values, dtype=np.float32)
    norm = float(np.linalg.norm(vector))
    if norm == 0:
        raise ValueError("Face embedding is empty")
    return vector / norm
