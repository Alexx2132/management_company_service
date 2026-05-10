from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.ticket import UserShortResponse


class BanMessageCreate(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)


class BanMessageResponse(BaseModel):
    id: int
    conversation_id: int
    sender_id: int
    message: str
    created_at: datetime
    sender: UserShortResponse | None = None

    class Config:
        from_attributes = True


class BanConversationResponse(BaseModel):
    id: int
    resident_id: int
    created_at: datetime
    updated_at: datetime
    resident: UserShortResponse | None = None
    messages: list[BanMessageResponse] = []

    class Config:
        from_attributes = True
