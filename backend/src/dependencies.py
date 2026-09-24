"""Reusable FastAPI dependencies, primarily authenticated-user resolution."""

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.models.users import User
from src.services.session_service import (
    ACCESS_COOKIE_NAME,
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    InvalidSessionError,
    authenticate_access_token,
    validate_csrf,
)


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """Validate the cookie session, CSRF token, and active Postgres user.

    Returning the User here lets protected routes share authentication and
    user scoping without duplicating token parsing or database lookups.
    """
    try:
        user, auth_session = authenticate_access_token(
            db,
            request.cookies.get(ACCESS_COOKIE_NAME),
        )
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            validate_csrf(
                auth_session,
                request.cookies.get(CSRF_COOKIE_NAME),
                request.headers.get(CSRF_HEADER_NAME),
            )
    except InvalidSessionError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication session is invalid",
        ) from exc
    return user
