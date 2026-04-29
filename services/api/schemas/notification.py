from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from models.models import NotificationChannel, NotificationStatus, NotificationType


# ── Notification Schemas ───────────────────────────────────────

class NotificationCreate(BaseModel):
    user_id: UUID
    type: NotificationType
    channel: NotificationChannel
    subject: Optional[str] = None
    body: str = Field(..., min_length=1)
    metadata: Optional[dict] = None
    scheduled_at: Optional[datetime] = None


class NotificationUpdate(BaseModel):
    is_read: Optional[bool] = None
    status: Optional[NotificationStatus] = None


class NotificationResponse(BaseModel):
    id: int
    user_id: UUID
    type: NotificationType
    channel: NotificationChannel
    status: NotificationStatus
    subject: Optional[str]
    body: str
    metadata: Optional[dict]
    is_read: bool
    scheduled_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PaginatedNotifications(BaseModel):
    items: list[NotificationResponse]
    total: int
    page: int
    page_size: int
