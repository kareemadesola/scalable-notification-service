from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from models.models import NotificationChannel, NotificationStatus
from schemas.notification import (
    NotificationCreate,
    NotificationResponse,
    NotificationUpdate,
)
from services.notification_service import (
    create_notification,
    get_notification_by_id,
    update_notification,
)

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.post("", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
async def create_notification_endpoint(
    data: NotificationCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Create and dispatch a notification.
    - Checks user preferences (channel opt-in, type opt-in, rate limits)
    - Saves to DB, then publishes to RabbitMQ (or writes directly for in-app)
    """
    notification = await create_notification(data, db)

    # Publish to RabbitMQ for async channels; in-app is already written to DB
    if notification.status == NotificationStatus.pending and notification.channel != NotificationChannel.inapp:
        publisher = request.app.state.publisher
        await publisher.publish(
            queue=notification.channel.value,
            payload={
                "notification_id": notification.id,
                "user_id": str(notification.user_id),
                "channel": notification.channel.value,
                "type": notification.type.value,
                "subject": notification.subject,
                "body": notification.body,
                "metadata": notification.metadata,
            },
        )
        notification.status = NotificationStatus.queued
        await db.flush()

    return notification


@router.get("/{notification_id}", response_model=NotificationResponse)
async def get_notification_endpoint(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Fetch a notification by ID."""
    return await get_notification_by_id(notification_id, db)


@router.patch("/{notification_id}", response_model=NotificationResponse)
async def update_notification_endpoint(
    notification_id: int,
    data: NotificationUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a notification — mark as read/unread or update status."""
    return await update_notification(notification_id, data, db)
