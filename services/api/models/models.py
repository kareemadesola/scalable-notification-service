import enum
import uuid

from sqlalchemy import (
    BigInteger, Boolean, Column, Enum, ForeignKey,
    SmallInteger, String, Text, TIMESTAMP
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from db.database import Base


class NotificationChannel(str, enum.Enum):
    email = "email"
    sms = "sms"
    push = "push"
    inapp = "inapp"


class NotificationType(str, enum.Enum):
    transactional = "transactional"
    promotional = "promotional"
    system_alert = "system_alert"


class NotificationStatus(str, enum.Enum):
    pending = "pending"
    queued = "queued"
    delivered = "delivered"
    failed = "failed"
    scheduled = "scheduled"


class DeliveryStatus(str, enum.Enum):
    success = "success"
    failed = "failed"
    retrying = "retrying"


class User(Base):
    __tablename__ = "users"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email        = Column(String(255), unique=True, nullable=False)
    phone        = Column(String(50))
    device_token = Column(String(512))
    first_name   = Column(String(100), nullable=False)
    last_name    = Column(String(100), nullable=False)
    created_at   = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at   = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    preferences   = relationship("UserPreference", back_populates="user", uselist=False)
    notifications = relationship("Notification", back_populates="user")


class UserPreference(Base):
    __tablename__ = "user_preferences"

    id      = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)

    email_enabled = Column(Boolean, nullable=False, default=True)
    sms_enabled   = Column(Boolean, nullable=False, default=True)
    push_enabled  = Column(Boolean, nullable=False, default=True)
    inapp_enabled = Column(Boolean, nullable=False, default=True)

    transactional = Column(Boolean, nullable=False, default=True)
    promotional   = Column(Boolean, nullable=False, default=True)
    system_alerts = Column(Boolean, nullable=False, default=True)

    max_promotional_per_day = Column(SmallInteger, nullable=False, default=5)
    dnd_start_hour          = Column(SmallInteger)
    dnd_end_hour            = Column(SmallInteger)

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", back_populates="preferences")


class Notification(Base):
    __tablename__ = "notifications"

    id           = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id      = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type         = Column(Enum(NotificationType, name="notification_type"), nullable=False)
    channel      = Column(Enum(NotificationChannel, name="notification_channel"), nullable=False)
    status       = Column(Enum(NotificationStatus, name="notification_status"), nullable=False, default=NotificationStatus.pending)
    subject      = Column(String(255))
    body         = Column(Text, nullable=False)
    extra_data   = Column("metadata", JSONB)
    is_read      = Column(Boolean, nullable=False, default=False)
    scheduled_at = Column(TIMESTAMP(timezone=True))
    created_at   = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at   = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", back_populates="notifications")
    logs = relationship("NotificationLog", back_populates="notification")


class NotificationLog(Base):
    __tablename__ = "notification_logs"

    id                = Column(BigInteger, primary_key=True, autoincrement=True)
    notification_id   = Column(BigInteger, ForeignKey("notifications.id", ondelete="CASCADE"), nullable=False)
    channel           = Column(Enum(NotificationChannel, name="notification_channel"), nullable=False)
    status            = Column(Enum(DeliveryStatus, name="delivery_status"), nullable=False)
    attempt_number    = Column(SmallInteger, nullable=False, default=1)
    provider_response = Column(Text)
    created_at        = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    notification = relationship("Notification", back_populates="logs")
