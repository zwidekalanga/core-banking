"""Authentication API endpoints for admin users."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.auth.dependencies import CurrentUser
from app.auth.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.config import get_settings
from app.dependencies import DBSession
from app.repositories.user_repository import UserRepository
from app.schemas.auth import RefreshRequest, TokenResponse, UserResponse

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(
    db: DBSession,
    form_data: OAuth2PasswordRequestForm = Depends(),  # pyright: ignore[reportCallInDefaultInitializer]
) -> TokenResponse:
    """Authenticate admin user and return JWT tokens."""
    repo = UserRepository(db)
    user = await repo.get_by_username(form_data.username)

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    settings = get_settings()
    return TokenResponse(
        access_token=create_access_token(
            user.id, user.role, username=user.username, email=user.email
        ),
        refresh_token=create_refresh_token(
            user.id, user.role, username=user.username, email=user.email
        ),
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    body: RefreshRequest,
    db: DBSession,
) -> TokenResponse:
    """Exchange a refresh token for a new access token."""
    try:
        payload = decode_token(body.refresh_token)
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        ) from err

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing subject",
        )
    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    settings = get_settings()
    return TokenResponse(
        access_token=create_access_token(
            user.id, user.role, username=user.username, email=user.email
        ),
        refresh_token=create_refresh_token(
            user.id, user.role, username=user.username, email=user.email
        ),
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: CurrentUser) -> UserResponse:
    """Return the authenticated admin user's profile."""
    return UserResponse.model_validate(current_user)
