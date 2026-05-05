import jwt
from fastapi.concurrency import run_in_threadpool
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.models.users import User

from src.services.auth_service import (
    create_access_token,
    create_refresh_token,
    decode_jwt,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: str
    name: str | None = None


class LoginRequest(BaseModel):
    email: str


class RefreshRequest(BaseModel):
    refresh_token: str


class GoogleSessionRequest(BaseModel):
    email: str
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


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
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
async def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
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
    user = await run_in_threadpool(
        lambda: db.query(User).filter(User.email == payload.email).first()
    )
    if user is None:
        user = User(
            email=payload.email,
            name=payload.name,
            avatar_url=payload.avatar_url,
            google_id=payload.google_id,
        )
        await run_in_threadpool(db.add, user)
    else:
        user.name = payload.name or user.name
        user.avatar_url = payload.avatar_url or user.avatar_url
        user.google_id = payload.google_id or user.google_id

    user.drive_access_token = payload.drive_access_token
    user.drive_refresh_token = payload.drive_refresh_token or user.drive_refresh_token
    await run_in_threadpool(db.commit)
    await run_in_threadpool(db.refresh, user)
    return build_token_response(user)


@router.post("/refresh", response_model=AccessTokenResponse)
def refresh(payload: RefreshRequest) -> AccessTokenResponse:
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
    
    return AccessTokenResponse(access_token=create_access_token(subject))
