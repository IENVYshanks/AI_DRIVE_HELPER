from datetime import datetime, timezone
from uuid import UUID
from fastapi.concurrency import run_in_threadpool
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.db.config import Settings, get_settings
from src.db.database import get_db
from src.models.users import User

from src.services.google_oauth_service import (
    GoogleOAuthError,
    GoogleOAuthSession,
    exchange_authorization_code,
)
from src.services.keys import get_tokens
from src.services.session_service import (
    ACCESS_COOKIE_NAME,
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    REFRESH_COOKIE_NAME,
    InvalidSessionError,
    SessionCredentials,
    authenticate_access_token,
    create_session,
    revoke_session,
    rotate_session,
    validate_csrf,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class GoogleSessionRequest(BaseModel):
    code: str = Field(min_length=1)
    redirect_uri: str = Field(min_length=1)


class UserResponse(BaseModel):
    id: UUID
    email: str
    name: str | None
    avatar_url: str | None


class GoogleSessionResponse(BaseModel):
    user: UserResponse


def user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        avatar_url=user.avatar_url,
    )


def set_session_cookies(
    response: Response,
    credentials: SessionCredentials,
    settings: Settings,
) -> None:
    """Set HttpOnly authentication cookies and one JS-readable CSRF cookie."""
    access_max_age = get_tokens().ACCESS_TOKEN_EXPIRE_MINUTES * 60
    refresh_max_age = max(
        0,
        int((credentials.refresh_expires_at - datetime.now(timezone.utc)).total_seconds()),
    )
    cookie_options = {
        "secure": settings.SESSION_COOKIE_SECURE,
        "samesite": settings.SESSION_COOKIE_SAMESITE,
    }
    response.set_cookie(
        ACCESS_COOKIE_NAME,
        credentials.access_token,
        httponly=True,
        max_age=access_max_age,
        path="/",
        **cookie_options,
    )
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        credentials.refresh_token,
        httponly=True,
        max_age=refresh_max_age,
        path="/auth",
        **cookie_options,
    )
    response.set_cookie(
        CSRF_COOKIE_NAME,
        credentials.csrf_token,
        httponly=False,
        max_age=refresh_max_age,
        path="/",
        **cookie_options,
    )
    response.headers["Cache-Control"] = "no-store"


def clear_session_cookies(response: Response, settings: Settings) -> None:
    cookie_options = {
        "secure": settings.SESSION_COOKIE_SECURE,
        "samesite": settings.SESSION_COOKIE_SAMESITE,
    }
    response.delete_cookie(ACCESS_COOKIE_NAME, path="/", **cookie_options)
    response.delete_cookie(REFRESH_COOKIE_NAME, path="/auth", **cookie_options)
    response.delete_cookie(CSRF_COOKIE_NAME, path="/", **cookie_options)
    response.headers["Cache-Control"] = "no-store"


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
    response: Response,
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
    session_credentials = await run_in_threadpool(create_session, db, user)
    set_session_cookies(response, session_credentials, settings)
    return GoogleSessionResponse(user=user_response(user))


@router.post("/refresh", status_code=status.HTTP_204_NO_CONTENT)
def refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> None:
    try:
        credentials = rotate_session(
            db,
            request.cookies.get(REFRESH_COOKIE_NAME),
            request.cookies.get(CSRF_COOKIE_NAME),
            request.headers.get(CSRF_HEADER_NAME),
        )
    except InvalidSessionError:
        response.status_code = status.HTTP_401_UNAUTHORIZED
        clear_session_cookies(response, settings)
        return None
    set_session_cookies(response, credentials, settings)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> None:
    try:
        _, auth_session = authenticate_access_token(
            db,
            request.cookies.get(ACCESS_COOKIE_NAME),
        )
        validate_csrf(
            auth_session,
            request.cookies.get(CSRF_COOKIE_NAME),
            request.headers.get(CSRF_HEADER_NAME),
        )
        revoke_session(db, auth_session)
    except InvalidSessionError:
        response.status_code = status.HTTP_401_UNAUTHORIZED
        clear_session_cookies(response, settings)
        return None
    clear_session_cookies(response, settings)


@router.get("/me", response_model=UserResponse)
def current_user(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> UserResponse:
    try:
        user, _ = authenticate_access_token(
            db,
            request.cookies.get(ACCESS_COOKIE_NAME),
        )
    except InvalidSessionError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication session is invalid",
        ) from exc
    response.headers["Cache-Control"] = "no-store"
    return user_response(user)
