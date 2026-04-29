from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
import httpx
import structlog

from auth import get_current_subject
from config import settings
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

router = APIRouter(
    prefix="/notifications",
    tags=["Notifications"],
    dependencies=[Depends(get_current_subject)],
)
logger = structlog.get_logger()


@router.post("", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
async def create_notification_endpoint(
    data: NotificationCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Create and dispatch a notification.
    - Checks user preferences (channel opt-in, type opt-in, rate limits)
    - Saves to DB, then publishes to RabbitMQ (or broadcasts directly for in-app)
    """
    notification = await create_notification(data, db)

    if notification.status == NotificationStatus.pending:
        if notification.channel == NotificationChannel.inapp:
            # Bypass queue — broadcast directly via WebSocket service
            try:
                async with httpx.AsyncClient() as client:
                    await client.post(
                        f"{settings.inapp_service_url}/inapp/broadcast/{notification.user_id}",
                        json={
                            "id": notification.id,
                            "subject": notification.subject,
                            "body": notification.body,
                            "metadata": notification.extra_data,
                        },
                        timeout=2.0,
                    )
            except Exception as exc:
                # Non-fatal — notification is in DB, client can poll inbox
                logger.warning("In-app broadcast failed", error=str(exc), notification_id=notification.id)
        else:
            # Async channels: commit to DB first, then publish to RabbitMQ.
            # This ensures the notification row exists before the processor
            # tries to write a notification_log referencing it.
            notification.status = NotificationStatus.queued
            await db.flush()
            await db.commit()
            await db.refresh(notification)

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
                    "metadata": notification.extra_data,
                },
            )

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
