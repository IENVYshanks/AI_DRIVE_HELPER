"""Tests for the existing-token encryption data migration."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from src.services.oauth_token_cipher import decrypt_oauth_token, encrypt_oauth_token


OAUTH_ENCRYPTION_KEY = "11" * 32
MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "20260924_0004_encrypt_drive_tokens.py"
)


def load_migration():
    spec = importlib.util.spec_from_file_location("encrypt_drive_tokens", MIGRATION_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load OAuth token migration")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def encryption_settings():
    return SimpleNamespace(
        OAUTH_TOKEN_ACTIVE_KEY_ID="primary",
        oauth_token_encryption_keys={
            "primary": bytes.fromhex(OAUTH_ENCRYPTION_KEY),
        },
    )


class OAuthTokenMigrationTests(TestCase):
    def test_upgrade_replaces_existing_plaintext_values(self) -> None:
        migration = load_migration()
        settings = encryption_settings()
        connection = Mock()
        selected_rows = Mock()
        selected_rows.mappings.return_value = [
            {
                "id": "user-id",
                "drive_access_token": "access-plaintext",
                "drive_refresh_token": "refresh-plaintext",
            }
        ]
        connection.execute.side_effect = [
            selected_rows,
            Mock(),
        ]

        with (
            patch.object(migration, "get_settings", return_value=settings),
            patch.object(migration.op, "get_bind", return_value=connection),
        ):
            migration.upgrade()

        update_values = connection.execute.call_args_list[1].args[1]
        self.assertNotIn("access-plaintext", update_values["access_token"])
        self.assertNotIn("refresh-plaintext", update_values["refresh_token"])
        self.assertEqual(
            decrypt_oauth_token(update_values["access_token"], settings),
            "access-plaintext",
        )
        self.assertEqual(
            decrypt_oauth_token(update_values["refresh_token"], settings),
            "refresh-plaintext",
        )

    def test_downgrade_restores_plaintext_values(self) -> None:
        migration = load_migration()
        settings = encryption_settings()
        connection = Mock()
        selected_rows = Mock()
        selected_rows.mappings.return_value = [
            {
                "id": "user-id",
                "drive_access_token": encrypt_oauth_token(
                    "access-plaintext",
                    settings,
                ),
                "drive_refresh_token": None,
            }
        ]
        connection.execute.side_effect = [
            selected_rows,
            Mock(),
        ]

        with (
            patch.object(migration, "get_settings", return_value=settings),
            patch.object(migration.op, "get_bind", return_value=connection),
        ):
            migration.downgrade()

        update_values = connection.execute.call_args_list[1].args[1]
        self.assertEqual(update_values["access_token"], "access-plaintext")
        self.assertIsNone(update_values["refresh_token"])
