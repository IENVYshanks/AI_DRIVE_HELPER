"""Unit tests for behavior-critical state transitions."""

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock

from src.services.folder_service import mark_folder_done, mark_folder_processing
from src.services.image_service import mark_image_done, mark_image_failed
from src.services.job_service import increment_job_failed, mark_job_done


class StateServiceTests(TestCase):
    def setUp(self) -> None:
        self.db = Mock()

    def test_image_done_commits_and_refreshes_by_default(self) -> None:
        image = SimpleNamespace()

        result = mark_image_done(self.db, image, face_count=3)

        self.assertIs(result, image)
        self.assertEqual(image.status, "done")
        self.assertEqual(image.face_count, 3)
        self.assertIsNone(image.error_message)
        self.db.commit.assert_called_once_with()
        self.db.refresh.assert_called_once_with(image)

    def test_auto_commit_false_leaves_transaction_to_caller(self) -> None:
        image = SimpleNamespace()

        mark_image_failed(self.db, image, error_message="unreadable", auto_commit=False)

        self.assertEqual(image.status, "failed")
        self.assertEqual(image.error_message, "unreadable")
        self.db.commit.assert_not_called()
        self.db.refresh.assert_not_called()

    def test_folder_processing_resets_previous_progress(self) -> None:
        folder = SimpleNamespace(processed_images=8, failed_images=2)

        mark_folder_processing(self.db, folder, auto_commit=False)

        self.assertEqual(folder.status, "processing")
        self.assertEqual(folder.processed_images, 0)
        self.assertEqual(folder.failed_images, 0)
        self.assertIsNone(folder.error_message)
        self.assertIsNone(folder.completed_at)

    def test_completion_preserves_recorded_failure(self) -> None:
        folder = SimpleNamespace(error_message="one file failed")
        job = SimpleNamespace(error_message="one file failed")

        mark_folder_done(self.db, folder, auto_commit=False)
        mark_job_done(self.db, job, auto_commit=False)

        self.assertEqual(folder.status, "failed")
        self.assertEqual(job.status, "failed")

    def test_job_failure_accumulates_counts_and_file_ids(self) -> None:
        job = SimpleNamespace(failed=1, failed_file_ids=["first"], error_message=None)

        increment_job_failed(
            self.db,
            job,
            file_id="second",
            error_message="decode failed",
            count=2,
            auto_commit=False,
        )

        self.assertEqual(job.failed, 3)
        self.assertEqual(job.failed_file_ids, ["first", "second"])
        self.assertEqual(job.error_message, "decode failed")
