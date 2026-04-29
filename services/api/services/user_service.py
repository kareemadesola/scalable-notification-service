from uuid import UUID

import structlog
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.models import UserPreference
from schemas.user import UserPreferenceUpdate
from services.preference_service import invalidate_preferences_cache

logger = structlog.get_logger()


async def get_preferences(user_id: UUID, db: AsyncSession) -> UserPreference:
    result = await db.execute(
        select(UserPreference).where(UserPreference.user_id == user_id)
    )
    prefs = result.scalar_one_or_none()
    if not prefs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Preferences for user {user_id} not found",
        )
    return prefs


async def update_preferences(
    user_id: UUID,
    data: UserPreferenceUpdate,
    db: AsyncSession,
) -> UserPreference:
    prefs = await get_preferences(user_id, db)

    # Only update fields that were explicitly provided
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(prefs, field, value)

    await db.flush()

    # Bust cache so next request gets fresh data
    await invalidate_preferences_cache(user_id)

    logger.info("User preferences updated", user_id=str(user_id))
    return prefs
