from pydantic import BaseModel
from datetime import datetime


class AnnouncementBase(BaseModel):
    title: str
    content: str
    target_house_id: int | None = None
    target_entrance_id: int | None = None
    is_important: bool = False
    is_active: bool = True


class AnnouncementCreate(AnnouncementBase):
    pass


class AnnouncementHistoryResponse(BaseModel):
    id: int
    announcement_id: int
    actor_id: int | None = None
    actor_name: str | None = None
    action: str
    old_value: str | None = None
    new_value: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class AnnouncementResponse(AnnouncementBase):
    id: int
    created_at: datetime
    author_id: int
    history: list[AnnouncementHistoryResponse] = []

    class Config:
        from_attributes = True
