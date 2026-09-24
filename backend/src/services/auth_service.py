"""Password hashing and short-lived JWT creation used by authentication routes.

Google authentication establishes identity, while this module issues the
application's short-lived access token bound to a revocable database session.
"""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from src.services.keys import get_tokens


tokens = get_tokens()
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    """Hash a password with bcrypt's per-password random salt."""
    password_bytes = password.encode("utf-8")
    hashed_password = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hashed_password.decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    """Safely compare a plaintext password with a stored bcrypt hash."""
    password_bytes = password.encode("utf-8")
    hashed_password_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(password_bytes, hashed_password_bytes)


def create_jwt(data: dict, expires_delta: timedelta | None = None) -> str:
    """Sign claims and add standard issued-at and expiry timestamps."""
    payload = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=tokens.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    return jwt.encode(payload, tokens.SECRET_KEY, algorithm=ALGORITHM)


def create_access_token(subject: str, session_id: str) -> str:
    """Issue the short-lived token accepted by protected API endpoints."""
    return create_jwt({"sub": subject, "sid": session_id, "type": "access"})


def decode_jwt(token: str) -> dict:
    """Verify a token's signature/expiry and return its claims."""
    return jwt.decode(token, tokens.SECRET_KEY, algorithms=[ALGORITHM])
