from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from schemas.notification import PaginatedNotifications, NotificationResponse
from schemas.user import UserPreferenceResponse, UserPreferenceUpdate
from services.notification_service import get_user_notifications
from services.user_service import get_preferences, update_preferences

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/{user_id}/notifications", response_model=PaginatedNotifications)
async def get_user_notifications_endpoint(
    user_id: UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Paginated inbox — all notifications for a user, newest first."""
    notifications, total = await get_user_notifications(user_id, db, page, page_size)
    return PaginatedNotifications(
        items=notifications,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{user_id}/preferences", response_model=UserPreferenceResponse)
async def get_user_preferences_endpoint(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Fetch notification preferences for a user."""
    return await get_preferences(user_id, db)


@router.put("/{user_id}/preferences", response_model=UserPreferenceResponse)
async def update_user_preferences_endpoint(
    user_id: UUID,
    data: UserPreferenceUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update notification preferences. Only provided fields are changed."""
    return await update_preferences(user_id, data, db)
