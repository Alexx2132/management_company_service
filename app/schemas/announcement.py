from pydantic import BaseModel
from datetime import datetime


class AnnouncementBase(BaseModel):
    title: str
    content: str
    target_house_id: int | None = None


class AnnouncementCreate(AnnouncementBase):
    pass


class AnnouncementResponse(AnnouncementBase):
    id: int
    created_at: datetime
    author_id: int

    class Config:
        from_attributes = True
