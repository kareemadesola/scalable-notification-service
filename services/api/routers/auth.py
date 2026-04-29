from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth import create_access_token, create_refresh_token, decode_refresh_token
from config import settings
from db.database import get_db
from models.models import User
from schemas.user import AccessTokenResponse, RefreshRequest, TokenRequest, TokenResponse
from sqlalchemy import select

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/token", response_model=TokenResponse, summary="Issue access and refresh tokens")
async def issue_token(body: TokenRequest, db: AsyncSession = Depends(get_db)):
    """
    Exchange a valid `user_id` for an access token and a refresh token.

    - **access_token** — short-lived (default 60 min), use as `Authorization: Bearer <token>`
    - **refresh_token** — long-lived (default 7 days), use with `POST /auth/refresh`
    """
    result = await db.execute(select(User).where(User.id == body.user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    subject = str(user.id)
    return TokenResponse(
        access_token=create_access_token(subject),
        refresh_token=create_refresh_token(subject),
        expires_in=settings.jwt_expire_minutes * 60,
        refresh_expires_in=settings.jwt_refresh_expire_days * 24 * 60 * 60,
    )


@router.post("/refresh", response_model=AccessTokenResponse, summary="Refresh an access token")
async def refresh_token(body: RefreshRequest):
    """
    Exchange a valid refresh token for a new access token.

    The refresh token itself is **not** rotated — use the same refresh token until it expires.
    """
    subject = decode_refresh_token(body.refresh_token)
    return AccessTokenResponse(
        access_token=create_access_token(subject),
        expires_in=settings.jwt_expire_minutes * 60,
    )
