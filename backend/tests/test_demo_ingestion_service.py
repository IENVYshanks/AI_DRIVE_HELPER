from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch
from uuid import uuid4

import numpy as np

from src.services.demo_ingestion_service import (
    DemoAssetAnalysis,
    build_demo_manifest,
    ingest_demo_assets,
)


def analysis(name: str, source: str, embeddings: list[list[float]]):
    return DemoAssetAnalysis(
        path=Path(name),
        source_id=f"demo:{source}",
        width=200,
        height=100,
        image_bytes=b"image",
        faces=[
            {
                "person_idx": index,
                "bbox_x": 20.0,
                "bbox_y": 10.0,
                "bbox_w": 40.0,
                "bbox_h": 30.0,
                "detection_score": 0.99,
                "embedding": np.asarray(embedding, dtype=np.float32),
            }
            for index, embedding in enumerate(embeddings)
        ],
    )


class DemoManifestTests(TestCase):
    def test_manifest_uses_percent_boxes_and_cross_photo_matches(self) -> None:
        manifest = build_demo_manifest(
            [
                analysis("one.jpg", "a" * 64, [[1.0, 0.0]]),
                analysis("two.jpg", "b" * 64, [[0.9, 0.1]]),
            ]
        )

        self.assertEqual(len(manifest["photos"]), 2)
        self.assertEqual(manifest["faces"][0]["bounds"], {
            "x": 10.0,
            "y": 10.0,
            "width": 20.0,
            "height": 30.0,
        })
        self.assertEqual(manifest["matches"][0]["photoId"], "b" * 16)
        self.assertGreater(manifest["matches"][0]["score"], 0.99)

    def test_manifest_never_exposes_embeddings(self) -> None:
        manifest = build_demo_manifest(
            [analysis("one.jpg", "a" * 64, [[1.0, 0.0]])]
        )

        self.assertNotIn("embedding", str(manifest))
        self.assertEqual(manifest["matches"], [])


def query_returning(value):
    query = Mock()
    query.filter.return_value.first.return_value = value
    return query


class DemoDatabaseIngestionTests(TestCase):
    def setUp(self) -> None:
        self.user = SimpleNamespace(id=uuid4(), email="demo@atelier.local")
        self.folder = SimpleNamespace(
            id=uuid4(),
            user_id=self.user.id,
            drive_folder_id="demo-assets-v1",
            status="pending",
            total_images=0,
            processed_images=0,
            failed_images=0,
            error_message=None,
            started_at=None,
            completed_at=None,
            updated_at=None,
        )

    @patch("src.services.demo_ingestion_service.assign_qdrant_point_ids")
    @patch("src.services.demo_ingestion_service.upsert_face_embeddings")
    @patch("src.services.demo_ingestion_service.replace_image_faces")
    @patch("src.services.demo_ingestion_service.storage_is_configured", return_value=False)
    def test_ingestion_persists_faces_and_completes_folder(
        self,
        _storage_configured,
        replace_faces,
        upsert_embeddings,
        _assign_points,
    ) -> None:
        db = Mock()
        db.query.side_effect = [
            query_returning(self.user),
            query_returning(self.folder),
            query_returning(None),
        ]
        db.get.return_value = self.folder

        face_row = SimpleNamespace(id=uuid4(), cluster_id=None)
        replace_faces.return_value = [face_row]
        upsert_embeddings.return_value = {str(face_row.id): str(face_row.id)}

        def assign_image_id() -> None:
            added_image = db.add.call_args.args[0]
            added_image.id = uuid4()

        db.flush.side_effect = assign_image_id
        item = analysis("one.jpg", "a" * 64, [[1.0, 0.0]])

        result = ingest_demo_assets(
            db,
            analyses=[item],
            user_email=self.user.email,
        )

        self.assertEqual(result.images_processed, 1)
        self.assertEqual(result.faces_processed, 1)
        self.assertEqual(self.folder.status, "done")
        self.assertEqual(self.folder.processed_images, 1)
        upsert_embeddings.assert_called_once()

    @patch("src.services.demo_ingestion_service.upsert_face_embeddings")
    def test_completed_asset_is_skipped_idempotently(self, upsert_embeddings) -> None:
        existing = SimpleNamespace(status="done", face_count=3)
        db = Mock()
        db.query.side_effect = [
            query_returning(self.user),
            query_returning(self.folder),
            query_returning(existing),
        ]
        db.get.return_value = self.folder

        result = ingest_demo_assets(
            db,
            analyses=[analysis("one.jpg", "a" * 64, [[1.0, 0.0]])],
            user_email=self.user.email,
        )

        self.assertEqual(result.images_processed, 0)
        self.assertEqual(result.images_skipped, 1)
        self.assertEqual(result.faces_processed, 3)
        upsert_embeddings.assert_not_called()

    @patch(
        "src.services.demo_ingestion_service.upload_image",
        side_effect=RuntimeError("storage unavailable"),
    )
    @patch("src.services.demo_ingestion_service.storage_is_configured", return_value=True)
    def test_provider_failure_marks_folder_failed(
        self, _storage_configured, _upload_image
    ) -> None:
        db = Mock()
        db.query.side_effect = [
            query_returning(self.user),
            query_returning(self.folder),
            query_returning(None),
        ]
        db.get.return_value = self.folder

        def assign_image_id() -> None:
            added_image = db.add.call_args.args[0]
            added_image.id = uuid4()

        db.flush.side_effect = assign_image_id

        with self.assertRaisesRegex(RuntimeError, "storage unavailable"):
            ingest_demo_assets(
                db,
                analyses=[analysis("one.jpg", "a" * 64, [[1.0, 0.0]])],
                user_email=self.user.email,
            )

        db.rollback.assert_called_once()
        self.assertEqual(self.folder.status, "failed")
        self.assertEqual(self.folder.error_message, "Demo ingestion failed")
