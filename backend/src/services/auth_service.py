import bcrypt
from src.services.keys import get_tokens
import jwt
from datetime import datetime, timedelta, timezone

tokens = get_tokens()
ALGORITHM = "HS256"

def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")
    hashed_password = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hashed_password.decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    password_bytes = password.encode("utf-8")
    hashed_password_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(password_bytes, hashed_password_bytes)


def create_jwt(data: dict, expires_delta: timedelta | None = None) -> str:
    payload = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=tokens.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    return jwt.encode(payload, tokens.SECRET_KEY, algorithm=ALGORITHM)


def create_access_token(subject: str) -> str:
    return create_jwt({"sub": subject, "type": "access"})


def create_refresh_token(subject: str) -> str:
    refresh_expires = timedelta(days=tokens.REFRESH_TOKEN_EXPIRE_DAYS)
    return create_jwt(
        {"sub": subject, "type": "refresh"},
        expires_delta=refresh_expires,
    )


def decode_jwt(token: str) -> dict:
    return jwt.decode(token, tokens.SECRET_KEY, algorithms=[ALGORITHM])
