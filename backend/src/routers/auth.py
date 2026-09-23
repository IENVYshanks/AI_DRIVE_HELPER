import jwt
from uuid import UUID
from fastapi.concurrency import run_in_threadpool
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.db.config import Settings, get_settings
from src.db.database import get_db
from src.models.users import User

from src.services.auth_service import (
    create_access_token,
    create_refresh_token,
    decode_jwt,
)
from src.services.google_oauth_service import (
    GoogleOAuthError,
    GoogleOAuthSession,
    exchange_authorization_code,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class RefreshRequest(BaseModel):
    refresh_token: str


class GoogleSessionRequest(BaseModel):
    code: str = Field(min_length=1)
    redirect_uri: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: UUID
    email: str
    name: str | None
    avatar_url: str | None


class GoogleSessionResponse(TokenResponse):
    user: UserResponse


def build_token_response(user: User) -> TokenResponse:
    subject = str(user.id)
    return TokenResponse(
        access_token=create_access_token(subject),
        refresh_token=create_refresh_token(subject),
    )


def persist_google_session(db: Session, google_session: GoogleOAuthSession) -> User:
    """Create or update a user by stable Google subject, never by email alone."""
    user = db.query(User).filter(User.google_id == google_session.subject).first()
    email_owner = db.query(User).filter(User.email == google_session.email).first()

    if user is None and email_owner is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account already uses this email; explicit account linking is required",
        )
    if user is not None and email_owner is not None and email_owner.id != user.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Google account email conflicts with another account",
        )
    if user is not None and user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not available",
        )

    if user is None:
        user = User(
            email=google_session.email,
            name=google_session.name,
            avatar_url=google_session.avatar_url,
            google_id=google_session.subject,
        )
        db.add(user)
    else:
        user.email = google_session.email
        user.name = google_session.name or user.name
        user.avatar_url = google_session.avatar_url or user.avatar_url

    user.drive_access_token = google_session.access_token
    user.drive_refresh_token = google_session.refresh_token or user.drive_refresh_token
    user.token_expires_at = google_session.expires_at
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Google account conflicts with an existing account",
        ) from exc
    db.refresh(user)
    return user


@router.post("/google/session", response_model=GoogleSessionResponse)
async def create_google_session(
    payload: GoogleSessionRequest,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> GoogleSessionResponse:
    configured_redirect = (settings.GOOGLE_REDIRECT_URI or "").rstrip("/")
    request_origin = (request.headers.get("origin") or "").rstrip("/")
    requested_with = request.headers.get("x-requested-with")
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET or not configured_redirect:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured",
        )
    if (
        payload.redirect_uri.rstrip("/") != configured_redirect
        or request_origin != configured_redirect
        or requested_with != "XMLHttpRequest"
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google OAuth request origin is invalid",
        )

    try:
        google_session = await run_in_threadpool(
            exchange_authorization_code,
            code=payload.code,
            redirect_uri=configured_redirect,
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
        )
    except GoogleOAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google authorization failed",
        ) from exc

    user = await run_in_threadpool(persist_google_session, db, google_session)
    tokens = build_token_response(user)
    return GoogleSessionResponse(
        **tokens.model_dump(),
        user=UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            avatar_url=user.avatar_url,
        ),
    )


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
