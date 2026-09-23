"""Tests for server-side Google OAuth exchange and claim validation."""

from unittest import TestCase
from unittest.mock import Mock, patch

import requests

from src.services.google_oauth_service import GoogleOAuthError, exchange_authorization_code


class GoogleOAuthServiceTests(TestCase):
    def setUp(self) -> None:
        self.token_response = Mock()
        self.token_response.raise_for_status.return_value = None
        self.token_response.json.return_value = {
            "id_token": "signed-id-token",
            "access_token": "drive-access-token",
            "refresh_token": "drive-refresh-token",
            "expires_in": 3600,
        }
        self.claims = {
            "iss": "https://accounts.google.com",
            "sub": "google-subject",
            "email": "user@example.com",
            "email_verified": True,
            "name": "Example User",
            "picture": "https://example.com/avatar.png",
        }

    def exchange(self):
        return exchange_authorization_code(
            code="one-time-code",
            redirect_uri="http://localhost:5173",
            client_id="client-id",
            client_secret="client-secret",
        )

    @patch("src.services.google_oauth_service.google_id_token.verify_oauth2_token")
    @patch("src.services.google_oauth_service.requests.post")
    def test_exchanges_code_and_returns_verified_identity(self, post, verify) -> None:
        post.return_value = self.token_response
        verify.return_value = self.claims

        session = self.exchange()

        self.assertEqual(session.subject, "google-subject")
        self.assertEqual(session.email, "user@example.com")
        self.assertEqual(session.access_token, "drive-access-token")
        self.assertEqual(session.refresh_token, "drive-refresh-token")
        verify.assert_called_once()
        post.assert_called_once_with(
            "https://oauth2.googleapis.com/token",
            data={
                "code": "one-time-code",
                "client_id": "client-id",
                "client_secret": "client-secret",
                "redirect_uri": "http://localhost:5173",
                "grant_type": "authorization_code",
            },
            timeout=30,
        )

    @patch("src.services.google_oauth_service.google_id_token.verify_oauth2_token")
    @patch("src.services.google_oauth_service.requests.post")
    def test_rejects_unverified_email(self, post, verify) -> None:
        post.return_value = self.token_response
        verify.return_value = {**self.claims, "email_verified": False}

        with self.assertRaisesRegex(GoogleOAuthError, "not verified"):
            self.exchange()

    @patch("src.services.google_oauth_service.google_id_token.verify_oauth2_token")
    @patch("src.services.google_oauth_service.requests.post")
    def test_rejects_wrong_authorized_party(self, post, verify) -> None:
        post.return_value = self.token_response
        verify.return_value = {**self.claims, "azp": "different-client"}

        with self.assertRaisesRegex(GoogleOAuthError, "authorized party"):
            self.exchange()

    @patch("src.services.google_oauth_service.requests.post")
    def test_hides_token_endpoint_failure_details(self, post) -> None:
        self.token_response.raise_for_status.side_effect = requests.HTTPError("sensitive body")
        post.return_value = self.token_response

        with self.assertRaisesRegex(GoogleOAuthError, "code exchange failed") as context:
            self.exchange()

        self.assertNotIn("sensitive body", str(context.exception))
