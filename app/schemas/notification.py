from datetime import datetime
from pydantic import BaseModel, Field


class NotificationResponse(BaseModel):
    id: int
    title: str
    message: str
    notif_type: str

    ticket_id: int | None = None
    complaint_id: int | None = None
    announcement_id: int | None = None

    is_read: bool
    created_at: datetime
    read_at: datetime | None = None

    class Config:
        from_attributes = True


class NotificationSummaryResponse(BaseModel):
    total: int
    unread: int
    unread_by_type: dict[str, int]


class MarkReadRequest(BaseModel):
    is_read: bool = True


class PushTokenRegisterRequest(BaseModel):
    token: str = Field(..., min_length=8, max_length=512)
    platform: str = Field(default="android", max_length=32)
    device_name: str | None = Field(default=None, max_length=160)


class PushTokenDeactivateRequest(BaseModel):
    token: str = Field(..., min_length=8, max_length=512)


class PushDeviceTokenResponse(BaseModel):
    id: int
    user_id: int
    platform: str
    role: str
    device_name: str | None = None
    is_active: bool
    last_seen_at: datetime

    class Config:
        from_attributes = True
