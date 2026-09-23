"""Server-side Google OAuth code exchange and identity verification."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import id_token as google_id_token

TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
VALID_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}


class GoogleOAuthError(ValueError):
    """Raised when Google cannot establish a trusted OAuth session."""


@dataclass(frozen=True)
class GoogleOAuthSession:
    """Verified Google identity and backend-only Drive credentials."""

    subject: str
    email: str
    name: str | None
    avatar_url: str | None
    access_token: str
    refresh_token: str | None
    expires_at: datetime


def _required_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise GoogleOAuthError(f"Google OAuth response did not include {key}")
    return value


def exchange_authorization_code(
    *,
    code: str,
    redirect_uri: str,
    client_id: str,
    client_secret: str,
) -> GoogleOAuthSession:
    """Exchange a one-time code and verify the signed Google ID token."""
    try:
        response = requests.post(
            TOKEN_ENDPOINT,
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=30,
        )
        response.raise_for_status()
        token_payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise GoogleOAuthError("Google authorization code exchange failed") from exc

    if not isinstance(token_payload, dict):
        raise GoogleOAuthError("Google OAuth response was invalid")

    raw_id_token = _required_string(token_payload, "id_token")
    access_token = _required_string(token_payload, "access_token")

    try:
        claims = google_id_token.verify_oauth2_token(
            raw_id_token,
            GoogleAuthRequest(),
            client_id,
        )
    except (GoogleAuthError, ValueError, TypeError) as exc:
        raise GoogleOAuthError("Google identity token verification failed") from exc

    if claims.get("iss") not in VALID_ISSUERS:
        raise GoogleOAuthError("Google identity token issuer is invalid")
    if claims.get("azp") not in (None, client_id):
        raise GoogleOAuthError("Google identity token authorized party is invalid")
    if claims.get("email_verified") is not True:
        raise GoogleOAuthError("Google account email is not verified")

    subject = _required_string(claims, "sub")
    email = _required_string(claims, "email")
    expires_in = token_payload.get("expires_in")
    if not isinstance(expires_in, (int, float)) or expires_in <= 0:
        raise GoogleOAuthError("Google OAuth response did not include a valid expiry")

    return GoogleOAuthSession(
        subject=subject,
        email=email,
        name=claims.get("name") if isinstance(claims.get("name"), str) else None,
        avatar_url=(
            claims.get("picture") if isinstance(claims.get("picture"), str) else None
        ),
        access_token=access_token,
        refresh_token=(
            token_payload.get("refresh_token")
            if isinstance(token_payload.get("refresh_token"), str)
            else None
        ),
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in),
    )
