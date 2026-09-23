"""Security-focused tests for the Google session endpoint."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.app import create_app
from src.db.config import get_settings
from src.db.database import get_db
from src.routers.auth import persist_google_session
from src.services.google_oauth_service import GoogleOAuthSession


def google_session() -> GoogleOAuthSession:
    return GoogleOAuthSession(
        subject="google-subject",
        email="user@example.com",
        name="Example User",
        avatar_url=None,
        access_token="drive-access-token",
        refresh_token="drive-refresh-token",
        expires_at=datetime.now(timezone.utc),
    )


class GoogleSessionTests(TestCase):
    def test_rejects_email_only_account_collision(self) -> None:
        existing = SimpleNamespace(id="existing-user")
        db = Mock()
        db.query.return_value.filter.return_value.first.side_effect = [None, existing]

        with self.assertRaises(HTTPException) as context:
            persist_google_session(db, google_session())

        self.assertEqual(context.exception.status_code, 409)
        db.commit.assert_not_called()

    def test_rejects_inactive_google_account(self) -> None:
        inactive = SimpleNamespace(
            id="inactive-user",
            status="disabled",
        )
        db = Mock()
        db.query.return_value.filter.return_value.first.side_effect = [inactive, inactive]

        with self.assertRaises(HTTPException) as context:
            persist_google_session(db, google_session())

        self.assertEqual(context.exception.status_code, 401)
        db.commit.assert_not_called()

    @patch("src.routers.auth.exchange_authorization_code")
    def test_rejects_request_from_unconfigured_origin_before_exchange(self, exchange) -> None:
        settings = get_settings().model_copy(
            update={
                "ENVIRONMENT": "test",
                "AUTO_CREATE_TABLES": False,
                "TRUSTED_HOSTS": "localhost,testserver",
                "GOOGLE_CLIENT_ID": "client-id",
                "GOOGLE_CLIENT_SECRET": "client-secret",
                "GOOGLE_REDIRECT_URI": "http://localhost:5173",
            }
        )
        app = create_app(settings)
        app.dependency_overrides[get_settings] = lambda: settings
        app.dependency_overrides[get_db] = lambda: Mock()

        with TestClient(app) as client:
            response = client.post(
                "/auth/google/session",
                json={"code": "one-time-code", "redirect_uri": "http://evil.example"},
                headers={
                    "Origin": "http://evil.example",
                    "X-Requested-With": "XMLHttpRequest",
                },
            )

        self.assertEqual(response.status_code, 400)
        exchange.assert_not_called()
