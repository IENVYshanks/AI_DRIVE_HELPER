"""Security regressions for ingestion error disclosure."""

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch
from uuid import uuid4

from src.ingestion.errors import (
    IMAGE_PROCESSING_FAILED_MESSAGE,
    INGESTION_FAILED_MESSAGE,
)
from src.ingestion.file_processor import _handle_processing_failure
from src.ingestion.job_runner import run_ingestion_job
from src.routers.ingestion import (
    FolderResponse,
    IngestedImageResponse,
    IngestionJobResponse,
    _to_ingested_image_response,
)


class IngestionErrorSafetyTests(TestCase):
    @patch("src.ingestion.file_processor.mark_drive_file_failed")
    def test_file_failure_persists_only_public_message(self, mark_failed) -> None:
        db = Mock()
        job = SimpleNamespace(id=uuid4())
        folder = SimpleNamespace(id=uuid4())
        secret = "postgresql://admin:secret@database/internal"

        message = _handle_processing_failure(
            db,
            job=job,
            folder=folder,
            drive_file={"id": "drive-file"},
            attempt_label="initial",
            exc=RuntimeError(secret),
        )

        self.assertEqual(message, IMAGE_PROCESSING_FAILED_MESSAGE)
        self.assertNotIn(secret, message)
        self.assertEqual(
            mark_failed.call_args.kwargs["error_message"],
            IMAGE_PROCESSING_FAILED_MESSAGE,
        )

    @patch("src.ingestion.job_runner.mark_job_failed")
    @patch("src.ingestion.job_runner.mark_folder_failed")
    @patch("src.ingestion.job_runner.mark_folder_processing")
    @patch("src.ingestion.job_runner.mark_job_running")
    @patch("src.ingestion.job_runner.drive_service.list_images_in_folder")
    def test_job_failure_persists_only_public_message(
        self,
        list_images,
        _mark_job_running,
        _mark_folder_processing,
        mark_folder_failed,
        mark_job_failed,
    ) -> None:
        db = Mock()
        job = SimpleNamespace(id=uuid4(), user_id=uuid4(), folder_id=uuid4())
        folder = SimpleNamespace(id=job.folder_id, drive_folder_id="drive-folder")
        job_query = Mock()
        folder_query = Mock()
        job_query.filter.return_value.first.return_value = job
        folder_query.filter.return_value.first.return_value = folder
        db.query.side_effect = [job_query, folder_query]
        list_images.side_effect = RuntimeError("redis://:secret@internal:6379")

        result = run_ingestion_job(db, job_id=job.id)

        self.assertIs(result, job)
        mark_folder_failed.assert_called_once_with(
            db,
            folder,
            INGESTION_FAILED_MESSAGE,
            auto_commit=False,
        )
        mark_job_failed.assert_called_once_with(
            db,
            job,
            INGESTION_FAILED_MESSAGE,
            auto_commit=False,
        )

    def test_response_models_mask_historical_internal_errors(self) -> None:
        secret = "provider request failed at /srv/private/path"
        folder = FolderResponse.model_validate(
            SimpleNamespace(
                id=uuid4(),
                drive_folder_id="drive-folder",
                folder_name="Photos",
                status="failed",
                total_images=1,
                processed_images=0,
                failed_images=1,
                error_message=secret,
            )
        )
        job = IngestionJobResponse.model_validate(
            SimpleNamespace(
                id=uuid4(),
                folder_id=folder.id,
                status="failed",
                job_type="full",
                total=1,
                processed=0,
                failed=1,
                error_message=secret,
                failed_file_ids=["drive-file"],
            )
        )

        self.assertEqual(folder.error_message, INGESTION_FAILED_MESSAGE)
        self.assertEqual(job.error_message, INGESTION_FAILED_MESSAGE)

    @patch("src.routers.ingestion.storage_is_configured", return_value=False)
    def test_image_response_masks_historical_internal_error(self, _storage) -> None:
        image = SimpleNamespace(
            id=uuid4(),
            folder_id=uuid4(),
            drive_file_id="drive-file",
            drive_file_name="photo.jpg",
            mime_type="image/jpeg",
            file_size_bytes=10,
            status="failed",
            face_count=0,
            error_message="s3://private-bucket/internal-key",
            storage_key=None,
        )

        response = _to_ingested_image_response(image)

        self.assertIsInstance(response, IngestedImageResponse)
        self.assertEqual(response.error_message, IMAGE_PROCESSING_FAILED_MESSAGE)
