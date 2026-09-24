"""Regression tests for image, Drive, inference, and workload limits."""

from io import BytesIO
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

import numpy as np
from PIL import Image as PILImage

from src.ingestion.file_processor import _validate_drive_file_limits
from src.services.drive_service import (
    DriveDownloadLimitExceeded,
    _LimitedBytesIO,
    list_images_in_folder,
)
from src.services.face_service import (
    FaceInferenceBusyError,
    InvalidImageError,
    decode_image_bytes,
    extract_faces_and_embeddings,
)
from src.services.ingestion_service import (
    DuplicateIngestionJobError,
    IngestionQuotaExceededError,
    start_ingestion_job,
)
from src.services.search_service import SearchRateLimitError, enforce_search_rate_limit


def image_bytes(width: int, height: int, image_format: str = "PNG") -> bytes:
    buffer = BytesIO()
    PILImage.new("RGB", (width, height), color="white").save(buffer, format=image_format)
    return buffer.getvalue()


def image_settings(**overrides):
    values = {
        "MAX_IMAGE_WIDTH": 100,
        "MAX_IMAGE_HEIGHT": 100,
        "MAX_IMAGE_PIXELS": 10_000,
        "MAX_IMAGE_FRAMES": 1,
        "MAX_INGESTION_IMAGE_BYTES": 1_024,
        "FACE_INFERENCE_WAIT_SECONDS": 1,
        "MAX_ACTIVE_INGESTION_JOBS_PER_USER": 2,
        "MAX_SEARCHES_PER_USER_PER_MINUTE": 10,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class ResourceLimitTests(TestCase):
    @patch("src.services.face_service.get_settings")
    def test_decodes_supported_image_within_limits(self, settings) -> None:
        settings.return_value = image_settings()

        decoded = decode_image_bytes(image_bytes(8, 6))

        self.assertEqual(decoded.shape, (6, 8, 3))

    @patch("src.services.face_service.get_settings")
    def test_rejects_decompression_size_before_numpy_allocation(self, settings) -> None:
        settings.return_value = image_settings(MAX_IMAGE_PIXELS=100)

        with self.assertRaisesRegex(InvalidImageError, "pixel count"):
            decode_image_bytes(image_bytes(20, 20))

    @patch("src.services.face_service.get_settings")
    def test_rejects_unsupported_actual_format(self, settings) -> None:
        settings.return_value = image_settings()

        with self.assertRaisesRegex(InvalidImageError, "Unsupported image format"):
            decode_image_bytes(image_bytes(4, 4, "BMP"))

    @patch("src.services.face_service.get_settings")
    @patch("src.services.face_service._get_inference_semaphore")
    @patch("src.services.face_service.decode_image_bytes")
    def test_rejects_work_when_inference_capacity_is_full(
        self,
        decode,
        get_semaphore,
        settings,
    ) -> None:
        decode.return_value = np.zeros((2, 2, 3), dtype=np.uint8)
        get_semaphore.return_value.acquire.return_value = False
        settings.return_value = image_settings()

        with self.assertRaises(FaceInferenceBusyError):
            extract_faces_and_embeddings(b"valid-image")

        get_semaphore.return_value.release.assert_not_called()

    def test_stream_buffer_never_exceeds_byte_limit(self) -> None:
        buffer = _LimitedBytesIO(4)
        buffer.write(b"1234")

        with self.assertRaises(DriveDownloadLimitExceeded):
            buffer.write(b"5")

        self.assertEqual(buffer.getvalue(), b"1234")

    @patch("src.services.drive_service.get_drive_service")
    @patch("src.services.drive_service.get_settings")
    def test_stops_enumerating_excessively_large_drive_folder(
        self,
        settings,
        get_drive_service,
    ) -> None:
        settings.return_value = SimpleNamespace(
            MAX_DRIVE_FOLDER_ITEMS=2,
            MAX_INGESTION_FILES_PER_JOB=10,
        )
        service = get_drive_service.return_value
        service.files.return_value.list.return_value.execute.return_value = {
            "files": [
                {"id": "1", "mimeType": "text/plain"},
                {"id": "2", "mimeType": "text/plain"},
                {"id": "3", "mimeType": "text/plain"},
            ]
        }

        with self.assertRaisesRegex(ValueError, "too many items"):
            list_images_in_folder("folder", "user", Mock())

    @patch("src.ingestion.file_processor.get_settings")
    def test_rejects_oversized_drive_metadata_before_download(self, settings) -> None:
        settings.return_value = image_settings(MAX_INGESTION_IMAGE_BYTES=10)

        with self.assertRaisesRegex(ValueError, "byte ingestion limit"):
            _validate_drive_file_limits({"size": "11"})

    @patch("src.services.ingestion_service.create_ingestion_job")
    @patch("src.services.ingestion_service.get_settings")
    def test_rejects_duplicate_active_folder_job(self, settings, create_job) -> None:
        settings.return_value = image_settings()
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace()

        with self.assertRaises(DuplicateIngestionJobError):
            start_ingestion_job(db, user_id="user", folder_id="folder")

        create_job.assert_not_called()

    @patch("src.services.ingestion_service.create_ingestion_job")
    @patch("src.services.ingestion_service.get_settings")
    def test_rejects_user_over_active_job_quota(self, settings, create_job) -> None:
        settings.return_value = image_settings(MAX_ACTIVE_INGESTION_JOBS_PER_USER=2)
        db = Mock()
        filtered = db.query.return_value.filter.return_value
        filtered.first.return_value = None
        filtered.count.return_value = 2

        with self.assertRaises(IngestionQuotaExceededError):
            start_ingestion_job(db, user_id="user", folder_id="folder")

        create_job.assert_not_called()

    @patch("src.services.search_service.get_settings")
    def test_rejects_user_over_search_rate_limit(self, settings) -> None:
        settings.return_value = image_settings(MAX_SEARCHES_PER_USER_PER_MINUTE=10)
        db = Mock()
        db.query.return_value.filter.return_value.count.return_value = 10

        with self.assertRaises(SearchRateLimitError):
            enforce_search_rate_limit(db, "user")
