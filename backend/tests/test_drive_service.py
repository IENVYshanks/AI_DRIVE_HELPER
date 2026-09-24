"""Tests for backend-only Google Drive credential refresh."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from src.services.drive_service import FOLDER_MIME_TYPE, get_drive_service, list_child_folders
from src.services.oauth_token_cipher import decrypt_oauth_token, encrypt_oauth_token


OAUTH_ENCRYPTION_KEY = "11" * 32


class DriveServiceTests(TestCase):
    @patch("src.services.drive_service.get_settings")
    @patch("src.services.drive_service.get_drive_service")
    def test_lists_paginated_child_folders_only(
        self,
        get_service,
        settings,
    ) -> None:
        settings.return_value = SimpleNamespace(MAX_DRIVE_FOLDER_ITEMS=10)
        first_page = {
            "files": [
                {
                    "id": "folder-b",
                    "name": "Beta",
                    "mimeType": FOLDER_MIME_TYPE,
                    "parents": ["root"],
                },
                {
                    "id": "image-a",
                    "name": "Photo",
                    "mimeType": "image/jpeg",
                    "parents": ["root"],
                },
            ],
            "nextPageToken": "next-page",
        }
        second_page = {
            "files": [
                {
                    "id": "folder-a",
                    "name": "Alpha",
                    "mimeType": FOLDER_MIME_TYPE,
                    "parents": ["root"],
                }
            ]
        }
        request = get_service.return_value.files.return_value.list
        request.return_value.execute.side_effect = [first_page, second_page]

        result = list_child_folders("root", "user-id", Mock())

        self.assertEqual(
            result,
            [
                {"id": "folder-b", "name": "Beta", "parent_id": "root"},
                {"id": "folder-a", "name": "Alpha", "parent_id": "root"},
            ],
        )
        self.assertEqual(request.call_count, 2)
        self.assertIn("mimeType=", request.call_args_list[0].kwargs["q"])

    @patch("src.services.drive_service.build")
    @patch("src.services.drive_service.GoogleAuthRequest")
    @patch("src.services.drive_service.Credentials")
    @patch("src.services.drive_service.get_settings")
    def test_refreshes_and_persists_expired_credentials(
        self,
        settings,
        credentials_class,
        google_request,
        build,
    ) -> None:
        encryption_settings = SimpleNamespace(
            GOOGLE_CLIENT_ID="client-id",
            GOOGLE_CLIENT_SECRET="client-secret",
            OAUTH_TOKEN_ACTIVE_KEY_ID="primary",
            oauth_token_encryption_keys={
                "primary": bytes.fromhex(OAUTH_ENCRYPTION_KEY),
            },
        )
        settings.return_value = encryption_settings
        user = SimpleNamespace(
            drive_access_token=encrypt_oauth_token(
                "expired-token",
                encryption_settings,
            ),
            drive_refresh_token=encrypt_oauth_token(
                "refresh-token",
                encryption_settings,
            ),
            token_expires_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = user
        credentials = Mock(
            expired=True,
            refresh_token="refresh-token",
            token="refreshed-token",
            expiry=datetime(2027, 1, 1),
        )
        credentials_class.return_value = credentials
        drive_client = Mock()
        build.return_value = drive_client

        result = get_drive_service("user-id", db)

        self.assertIs(result, drive_client)
        credentials.refresh.assert_called_once_with(google_request.return_value)
        self.assertNotIn("refreshed-token", user.drive_access_token)
        self.assertEqual(
            decrypt_oauth_token(user.drive_access_token, encryption_settings),
            "refreshed-token",
        )
        self.assertEqual(user.token_expires_at.tzinfo, timezone.utc)
        db.commit.assert_called_once_with()
