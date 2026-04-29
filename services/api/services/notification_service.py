from uuid import UUID

import structlog
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.models import Notification, NotificationStatus, UserPreference
from schemas.notification import NotificationCreate, NotificationUpdate
from services.preference_service import (
    get_user_preferences,
    is_channel_allowed,
    is_rate_limited,
    is_type_allowed,
)

logger = structlog.get_logger()


async def create_notification(
    data: NotificationCreate,
    db: AsyncSession,
) -> Notification:
    # 1. Fetch user preferences
    prefs: UserPreference | None = await get_user_preferences(data.user_id, db)

    if prefs:
        # 2. Check channel opt-in
        if not is_channel_allowed(prefs, data.channel.value):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"User has disabled {data.channel.value} notifications",
            )

        # 3. Check notification type opt-in
        if not is_type_allowed(prefs, data.type.value):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"User has opted out of {data.type.value} notifications",
            )

        # 4. Rate limit check for promotional
        if await is_rate_limited(data.user_id, data.type.value, prefs.max_promotional_per_day):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Daily promotional notification limit reached for this user",
            )

    # 5. Determine initial status
    initial_status = (
        NotificationStatus.scheduled
        if data.scheduled_at
        else NotificationStatus.pending
    )

    notification = Notification(
        user_id=data.user_id,
        type=data.type,
        channel=data.channel,
        status=initial_status,
        subject=data.subject,
        body=data.body,
        extra_data=data.extra_data,
        scheduled_at=data.scheduled_at,
    )
    db.add(notification)
    await db.flush()  # get the generated id before commit

    logger.info(
        "Notification created",
        notification_id=notification.id,
        channel=data.channel.value,
        type=data.type.value,
        user_id=str(data.user_id),
    )
    return notification


async def get_notification_by_id(
    notification_id: int, db: AsyncSession
) -> Notification:
    result = await db.execute(
        select(Notification).where(Notification.id == notification_id)
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification {notification_id} not found",
        )
    return notification


async def get_user_notifications(
    user_id: UUID,
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Notification], int]:
    offset = (page - 1) * page_size

    total_result = await db.execute(
        select(func.count()).where(Notification.user_id == user_id)
    )
    total = total_result.scalar_one()

    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    notifications = result.scalars().all()
    return list(notifications), total


async def update_notification(
    notification_id: int,
    data: NotificationUpdate,
    db: AsyncSession,
) -> Notification:
    notification = await get_notification_by_id(notification_id, db)

    if data.is_read is not None:
        notification.is_read = data.is_read
    if data.status is not None:
        notification.status = data.status

    await db.flush()
    logger.info("Notification updated", notification_id=notification_id)
    return notification
