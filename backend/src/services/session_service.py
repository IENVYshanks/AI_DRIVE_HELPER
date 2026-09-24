"""Revocable server-side sessions with rotating opaque refresh credentials."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets
from uuid import UUID, uuid4

import jwt
from sqlalchemy.orm import Session

from src.models.auth_session import AuthSession
from src.models.users import User
from src.services.auth_service import create_access_token, decode_jwt
from src.services.keys import get_tokens

ACCESS_COOKIE_NAME = "app_access"
REFRESH_COOKIE_NAME = "app_refresh"
CSRF_COOKIE_NAME = "app_csrf"
CSRF_HEADER_NAME = "X-CSRF-Token"


class InvalidSessionError(ValueError):
    """Raised when session credentials are absent, expired, or invalid."""


class RefreshReuseError(InvalidSessionError):
    """Raised after a previously rotated refresh credential is replayed."""


@dataclass(frozen=True)
class SessionCredentials:
    access_token: str
    refresh_token: str
    csrf_token: str
    refresh_expires_at: datetime


def _hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _new_secret() -> str:
    return secrets.token_urlsafe(32)


def _refresh_cookie_value(session_id: UUID, secret: str) -> str:
    return f"{session_id}.{secret}"


def _parse_refresh_cookie(value: str | None) -> tuple[UUID, str]:
    if not value or "." not in value:
        raise InvalidSessionError("Refresh session is missing")
    raw_session_id, secret = value.split(".", 1)
    if not secret:
        raise InvalidSessionError("Refresh session is invalid")
    try:
        return UUID(raw_session_id), secret
    except ValueError as exc:
        raise InvalidSessionError("Refresh session is invalid") from exc


def create_session(db: Session, user: User) -> SessionCredentials:
    """Persist a hashed refresh credential and return cookie values once."""
    token_settings = get_tokens()
    session_id = uuid4()
    refresh_secret = _new_secret()
    csrf_secret = _new_secret()
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=token_settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    auth_session = AuthSession(
        id=session_id,
        user_id=user.id,
        refresh_token_hash=_hash_secret(refresh_secret),
        csrf_token_hash=_hash_secret(csrf_secret),
        expires_at=expires_at,
    )
    db.add(auth_session)
    db.commit()
    return SessionCredentials(
        access_token=create_access_token(str(user.id), str(session_id)),
        refresh_token=_refresh_cookie_value(session_id, refresh_secret),
        csrf_token=csrf_secret,
        refresh_expires_at=expires_at,
    )


def _active_session(
    db: Session,
    session_id: UUID,
    *,
    for_update: bool = False,
) -> AuthSession:
    query = db.query(AuthSession).filter(AuthSession.id == session_id)
    if for_update:
        query = query.with_for_update()
    auth_session = query.first()
    now = datetime.now(timezone.utc)
    expires_at = auth_session.expires_at if auth_session is not None else None
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if (
        auth_session is None
        or auth_session.revoked_at is not None
        or expires_at is None
        or expires_at <= now
    ):
        raise InvalidSessionError("Session is not active")
    return auth_session


def validate_csrf(auth_session: AuthSession, cookie_value: str | None, header_value: str | None) -> None:
    """Require a matching double-submit token that is also bound to the session."""
    if not cookie_value or not header_value or not hmac.compare_digest(cookie_value, header_value):
        raise InvalidSessionError("CSRF validation failed")
    if not hmac.compare_digest(_hash_secret(cookie_value), auth_session.csrf_token_hash):
        raise InvalidSessionError("CSRF validation failed")


def authenticate_access_token(db: Session, token: str | None) -> tuple[User, AuthSession]:
    """Resolve a short-lived cookie JWT to its active server-side session and user."""
    if not token:
        raise InvalidSessionError("Access session is missing")
    try:
        payload = decode_jwt(token)
        if payload.get("type") != "access":
            raise InvalidSessionError("Access session is invalid")
        user_id = UUID(payload["sub"])
        session_id = UUID(payload["sid"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise InvalidSessionError("Access session is invalid") from exc

    auth_session = _active_session(db, session_id)
    if auth_session.user_id != user_id:
        raise InvalidSessionError("Access session is invalid")
    user = db.query(User).filter(User.id == user_id).first()
    if user is None or user.status != "active":
        raise InvalidSessionError("User is not available")
    return user, auth_session


def rotate_session(
    db: Session,
    refresh_cookie: str | None,
    csrf_cookie: str | None,
    csrf_header: str | None,
) -> SessionCredentials:
    """Rotate a refresh credential and revoke the session when reuse is detected."""
    session_id, presented_secret = _parse_refresh_cookie(refresh_cookie)
    auth_session = _active_session(db, session_id, for_update=True)
    validate_csrf(auth_session, csrf_cookie, csrf_header)
    presented_hash = _hash_secret(presented_secret)

    is_previous_token = bool(
        auth_session.previous_refresh_token_hash
        and hmac.compare_digest(presented_hash, auth_session.previous_refresh_token_hash)
    )
    if is_previous_token or not hmac.compare_digest(
        presented_hash, auth_session.refresh_token_hash
    ):
        auth_session.revoked_at = datetime.now(timezone.utc)
        db.commit()
        raise RefreshReuseError("Refresh credential reuse detected")

    user = db.query(User).filter(User.id == auth_session.user_id).first()
    if user is None or user.status != "active":
        raise InvalidSessionError("User is not available")

    token_settings = get_tokens()
    refresh_secret = _new_secret()
    csrf_secret = _new_secret()
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=token_settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    auth_session.previous_refresh_token_hash = auth_session.refresh_token_hash
    auth_session.refresh_token_hash = _hash_secret(refresh_secret)
    auth_session.csrf_token_hash = _hash_secret(csrf_secret)
    auth_session.expires_at = expires_at
    db.commit()
    return SessionCredentials(
        access_token=create_access_token(str(user.id), str(auth_session.id)),
        refresh_token=_refresh_cookie_value(auth_session.id, refresh_secret),
        csrf_token=csrf_secret,
        refresh_expires_at=expires_at,
    )


def revoke_session(db: Session, auth_session: AuthSession) -> None:
    """Revoke one browser session without affecting the user's other devices."""
    if auth_session.revoked_at is None:
        auth_session.revoked_at = datetime.now(timezone.utc)
        db.commit()
