"""Tests for hashed, rotating, revocable browser sessions."""

from datetime import datetime, timedelta, timezone
import hashlib
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch
from uuid import uuid4

from src.models.auth_session import AuthSession
from src.services.session_service import (
    RefreshReuseError,
    create_session,
    rotate_session,
)


def secret_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class SessionServiceTests(TestCase):
    @patch("src.services.session_service.create_access_token", return_value="access-jwt")
    @patch("src.services.session_service._new_secret", side_effect=["refresh-secret", "csrf-secret"])
    @patch("src.services.session_service.get_tokens")
    def test_create_session_stores_only_hashed_secrets(
        self,
        token_settings,
        _new_secret,
        create_access_token,
    ) -> None:
        token_settings.return_value = SimpleNamespace(REFRESH_TOKEN_EXPIRE_DAYS=7)
        user = SimpleNamespace(id=uuid4())
        db = Mock()

        credentials = create_session(db, user)

        stored = db.add.call_args.args[0]
        self.assertIsInstance(stored, AuthSession)
        self.assertEqual(stored.refresh_token_hash, secret_hash("refresh-secret"))
        self.assertEqual(stored.csrf_token_hash, secret_hash("csrf-secret"))
        self.assertNotIn("refresh-secret", stored.refresh_token_hash)
        self.assertTrue(credentials.refresh_token.endswith(".refresh-secret"))
        self.assertEqual(credentials.csrf_token, "csrf-secret")
        create_access_token.assert_called_once_with(str(user.id), str(stored.id))
        db.commit.assert_called_once_with()

    def test_replayed_refresh_token_revokes_session(self) -> None:
        session_id = uuid4()
        auth_session = SimpleNamespace(
            id=session_id,
            user_id=uuid4(),
            refresh_token_hash=secret_hash("current-secret"),
            previous_refresh_token_hash=secret_hash("replayed-secret"),
            csrf_token_hash=secret_hash("csrf-secret"),
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
            revoked_at=None,
        )
        db = Mock()
        db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = (
            auth_session
        )

        with self.assertRaises(RefreshReuseError):
            rotate_session(
                db,
                f"{session_id}.replayed-secret",
                "csrf-secret",
                "csrf-secret",
            )

        self.assertIsNotNone(auth_session.revoked_at)
        db.commit.assert_called_once_with()

    @patch("src.services.session_service.create_access_token", return_value="new-access-jwt")
    @patch("src.services.session_service._new_secret", side_effect=["new-refresh", "new-csrf"])
    @patch("src.services.session_service.get_tokens")
    def test_refresh_rotates_credentials_atomically(
        self,
        token_settings,
        _new_secret,
        create_access_token,
    ) -> None:
        token_settings.return_value = SimpleNamespace(REFRESH_TOKEN_EXPIRE_DAYS=7)
        session_id = uuid4()
        user_id = uuid4()
        old_hash = secret_hash("current-secret")
        auth_session = SimpleNamespace(
            id=session_id,
            user_id=user_id,
            refresh_token_hash=old_hash,
            previous_refresh_token_hash=None,
            csrf_token_hash=secret_hash("csrf-secret"),
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
            revoked_at=None,
        )
        user = SimpleNamespace(id=user_id, status="active")
        session_query = Mock()
        session_query.filter.return_value.with_for_update.return_value.first.return_value = (
            auth_session
        )
        user_query = Mock()
        user_query.filter.return_value.first.return_value = user
        db = Mock()
        db.query.side_effect = [session_query, user_query]

        credentials = rotate_session(
            db,
            f"{session_id}.current-secret",
            "csrf-secret",
            "csrf-secret",
        )

        self.assertEqual(auth_session.previous_refresh_token_hash, old_hash)
        self.assertEqual(auth_session.refresh_token_hash, secret_hash("new-refresh"))
        self.assertEqual(auth_session.csrf_token_hash, secret_hash("new-csrf"))
        self.assertTrue(credentials.refresh_token.endswith(".new-refresh"))
        create_access_token.assert_called_once_with(str(user_id), str(session_id))
        db.commit.assert_called_once_with()
