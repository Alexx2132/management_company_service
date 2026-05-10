from datetime import datetime

from pydantic import BaseModel

from app.models.house_info import HouseEventType, HouseScheduleType


class HouseEventBase(BaseModel):
    house_id: int | None = None
    title: str
    description: str | None = None
    event_type: HouseEventType
    starts_at: datetime
    ends_at: datetime | None = None
    is_active: bool = True


class HouseEventCreate(HouseEventBase):
    pass


class HouseEventUpdate(BaseModel):
    house_id: int | None = None
    title: str | None = None
    description: str | None = None
    event_type: HouseEventType | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    is_active: bool | None = None


class HouseEventResponse(HouseEventBase):
    id: int
    author_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class EmergencyContactBase(BaseModel):
    house_id: int | None = None
    title: str
    phone: str
    description: str | None = None
    is_24_7: bool = False
    is_active: bool = True
    sort_order: int = 0


class EmergencyContactCreate(EmergencyContactBase):
    pass


class EmergencyContactUpdate(BaseModel):
    house_id: int | None = None
    title: str | None = None
    phone: str | None = None
    description: str | None = None
    is_24_7: bool | None = None
    is_active: bool | None = None
    sort_order: int | None = None


class EmergencyContactResponse(EmergencyContactBase):
    id: int
    author_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class HouseScheduleBase(BaseModel):
    house_id: int | None = None
    title: str
    description: str | None = None
    schedule_type: HouseScheduleType
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    frequency_text: str | None = None
    is_active: bool = True


class HouseScheduleCreate(HouseScheduleBase):
    pass


class HouseScheduleUpdate(BaseModel):
    house_id: int | None = None
    title: str | None = None
    description: str | None = None
    schedule_type: HouseScheduleType | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    frequency_text: str | None = None
    is_active: bool | None = None


class HouseScheduleResponse(HouseScheduleBase):
    id: int
    author_id: int
    created_at: datetime

    class Config:
        from_attributes = True