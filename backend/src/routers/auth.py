import jwt
import requests
from uuid import UUID
from fastapi.concurrency import run_in_threadpool
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.db.config import get_settings
from src.db.database import get_db
from src.models.users import User

from src.services.auth_service import (
    create_access_token,
    create_refresh_token,
    decode_jwt,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def require_insecure_email_auth() -> None:
    """Allow passwordless email endpoints only in explicitly enabled environments."""
    if not get_settings().ALLOW_INSECURE_EMAIL_AUTH:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


class RegisterRequest(BaseModel):
    email: str
    name: str | None = None


class LoginRequest(BaseModel):
    email: str


class RefreshRequest(BaseModel):
    refresh_token: str


class GoogleSessionRequest(BaseModel):
    email: str | None = None
    name: str | None = None
    avatar_url: str | None = None
    google_id: str | None = None
    drive_access_token: str
    drive_refresh_token: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def build_token_response(user: User) -> TokenResponse:
    subject = str(user.id)
    return TokenResponse(
        access_token=create_access_token(subject),
        refresh_token=create_refresh_token(subject),
    )


def fetch_google_userinfo(access_token: str) -> dict:
    response = requests.get(
        "https://www.googleapis.com/oauth2/v3/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    if response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google access token",
        )
    payload = response.json()
    if not payload.get("email"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google account email is required",
        )
    return payload


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    _: None = Depends(require_insecure_email_auth),
    db: Session = Depends(get_db),
) -> TokenResponse:
    existing_user = await run_in_threadpool(
        lambda: db.query(User).filter(User.email == payload.email).first()
    )
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    user = User(
        email=payload.email,
        name=payload.name,
    )
    await run_in_threadpool(db.add, user)
    await run_in_threadpool(db.commit)
    await run_in_threadpool(db.refresh, user)

    return build_token_response(user)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    _: None = Depends(require_insecure_email_auth),
    db: Session = Depends(get_db),
) -> TokenResponse:
    user = await run_in_threadpool(
        lambda: db.query(User).filter(User.email == payload.email).first()
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return build_token_response(user)


@router.post("/google/session", response_model=TokenResponse)
async def create_google_session(
    payload: GoogleSessionRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    google_user = await run_in_threadpool(fetch_google_userinfo, payload.drive_access_token)
    email = google_user["email"]
    name = google_user.get("name") or payload.name
    avatar_url = google_user.get("picture") or payload.avatar_url
    google_id = google_user.get("sub") or payload.google_id

    user = await run_in_threadpool(
        lambda: db.query(User).filter(User.email == email).first()
    )
    if user is None:
        user = User(
            email=email,
            name=name,
            avatar_url=avatar_url,
            google_id=google_id,
        )
        await run_in_threadpool(db.add, user)
    else:
        user.name = name or user.name
        user.avatar_url = avatar_url or user.avatar_url
        user.google_id = google_id or user.google_id

    user.drive_access_token = payload.drive_access_token
    user.drive_refresh_token = payload.drive_refresh_token or user.drive_refresh_token
    await run_in_threadpool(db.commit)
    await run_in_threadpool(db.refresh, user)
    return build_token_response(user)


@router.post("/refresh", response_model=AccessTokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> AccessTokenResponse:
    try:
        token_payload = decode_jwt(payload.refresh_token)
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        ) from exc

    if token_payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token required",
        )

    subject = token_payload.get("sub")
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token subject missing",
        )
    try:
        user_id = UUID(subject)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token subject",
        ) from exc

    user = db.query(User).filter(User.id == user_id, User.status == "active").first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not available",
        )

    return AccessTokenResponse(access_token=create_access_token(subject))
