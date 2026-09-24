"""Security-focused tests for the Google session endpoint."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch
from uuid import uuid4

from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.app import create_app
from src.db.config import get_settings
from src.db.database import get_db
from src.routers.auth import persist_google_session
from src.services.google_oauth_service import GoogleOAuthSession
from src.services.session_service import InvalidSessionError, SessionCredentials


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

    @patch("src.routers.auth.create_session")
    @patch("src.routers.auth.persist_google_session")
    @patch("src.routers.auth.exchange_authorization_code")
    def test_google_login_returns_profile_and_http_only_session_cookies(
        self,
        exchange,
        persist,
        create_session,
    ) -> None:
        settings = get_settings().model_copy(
            update={
                "ENVIRONMENT": "test",
                "AUTO_CREATE_TABLES": False,
                "TRUSTED_HOSTS": "localhost,testserver",
                "GOOGLE_CLIENT_ID": "client-id",
                "GOOGLE_CLIENT_SECRET": "client-secret",
                "GOOGLE_REDIRECT_URI": "http://localhost:5173",
                "SESSION_COOKIE_SECURE": False,
            }
        )
        app = create_app(settings)
        app.dependency_overrides[get_settings] = lambda: settings
        app.dependency_overrides[get_db] = lambda: Mock()
        user_id = uuid4()
        persist.return_value = SimpleNamespace(
            id=user_id,
            email="user@example.com",
            name="Example User",
            avatar_url=None,
        )
        exchange.return_value = google_session()
        create_session.return_value = SessionCredentials(
            access_token="access-jwt",
            refresh_token=f"{uuid4()}.refresh-secret",
            csrf_token="csrf-secret",
            refresh_expires_at=datetime.now(timezone.utc),
        )

        with TestClient(app) as client:
            response = client.post(
                "/auth/google/session",
                json={
                    "code": "one-time-code",
                    "redirect_uri": "http://localhost:5173",
                },
                headers={
                    "Origin": "http://localhost:5173",
                    "X-Requested-With": "XMLHttpRequest",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "user": {
                "id": str(user_id),
                "email": "user@example.com",
                "name": "Example User",
                "avatar_url": None,
            }
        })
        self.assertNotIn("access_token", response.text)
        cookies = response.headers.get_list("set-cookie")
        access_cookie = next(value for value in cookies if value.startswith("app_access="))
        refresh_cookie = next(value for value in cookies if value.startswith("app_refresh="))
        csrf_cookie = next(value for value in cookies if value.startswith("app_csrf="))
        self.assertIn("HttpOnly", access_cookie)
        self.assertIn("HttpOnly", refresh_cookie)
        self.assertNotIn("HttpOnly", csrf_cookie)

    @patch("src.routers.auth.rotate_session", side_effect=InvalidSessionError("invalid"))
    def test_invalid_refresh_clears_all_session_cookies(self, _rotate) -> None:
        settings = get_settings().model_copy(
            update={
                "ENVIRONMENT": "test",
                "AUTO_CREATE_TABLES": False,
                "TRUSTED_HOSTS": "localhost,testserver",
                "SESSION_COOKIE_SECURE": False,
            }
        )
        app = create_app(settings)
        app.dependency_overrides[get_settings] = lambda: settings
        app.dependency_overrides[get_db] = lambda: Mock()

        with TestClient(app) as client:
            response = client.post("/auth/refresh")

        self.assertEqual(response.status_code, 401)
        cookies = response.headers.get_list("set-cookie")
        self.assertTrue(any(value.startswith("app_access=") for value in cookies))
        self.assertTrue(any(value.startswith("app_refresh=") for value in cookies))
        self.assertTrue(any(value.startswith("app_csrf=") for value in cookies))
        self.assertTrue(all("Max-Age=0" in value for value in cookies))
