from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr


# ── Auth Schemas ───────────────────────────────────────────────

class TokenRequest(BaseModel):
    user_id: UUID


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until access token expires


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


# ── User Schemas ───────────────────────────────────────────────

class UserCreate(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str
    phone: Optional[str] = None
    device_token: Optional[str] = None


class UserResponse(BaseModel):
    id: UUID
    email: str
    first_name: str
    last_name: str
    phone: Optional[str]
    device_token: Optional[str]

    model_config = {"from_attributes": True}


# ── User Preference Schemas ────────────────────────────────────

class UserPreferenceUpdate(BaseModel):
    email_enabled: Optional[bool] = None
    sms_enabled: Optional[bool] = None
    push_enabled: Optional[bool] = None
    inapp_enabled: Optional[bool] = None
    transactional: Optional[bool] = None
    promotional: Optional[bool] = None
    system_alerts: Optional[bool] = None
    max_promotional_per_day: Optional[int] = None
    dnd_start_hour: Optional[int] = None
    dnd_end_hour: Optional[int] = None


class UserPreferenceResponse(BaseModel):
    id: UUID
    user_id: UUID
    email_enabled: bool
    sms_enabled: bool
    push_enabled: bool
    inapp_enabled: bool
    transactional: bool
    promotional: bool
    system_alerts: bool
    max_promotional_per_day: int
    dnd_start_hour: Optional[int]
    dnd_end_hour: Optional[int]

    model_config = {"from_attributes": True}
