from datetime import datetime

from pydantic import BaseModel, Field


class MessageUserResponse(BaseModel):
    id: int
    full_name: str
    role: str
    login: str | None = None
    contact_phone: str | None = None
    house_address: str | None = None
    entrance_number: int | None = None
    apartment_number: str | None = None

    class Config:
        from_attributes = True


class MessageFileResponse(BaseModel):
    id: int
    message_id: int
    file_url: str
    original_filename: str | None = None
    content_type: str | None = None
    size_bytes: int | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class MessageItemResponse(BaseModel):
    id: int
    conversation_id: int
    sender_id: int
    sender: MessageUserResponse | None = None
    body: str
    created_at: datetime
    files: list[MessageFileResponse] = []

    class Config:
        from_attributes = True


class MessageParticipantResponse(BaseModel):
    user_id: int
    user: MessageUserResponse | None = None
    muted_until: datetime | None = None
    last_read_at: datetime | None = None

    class Config:
        from_attributes = True


class MessageConversationResponse(BaseModel):
    id: int
    title: str | None = None
    context_type: str
    ticket_id: int | None = None
    created_by_id: int
    is_closed: bool
    unread_count: int = 0
    muted_until: datetime | None = None
    created_at: datetime
    updated_at: datetime
    participants: list[MessageParticipantResponse] = []
    messages: list[MessageItemResponse] = []

    class Config:
        from_attributes = True


class MessageConversationCreate(BaseModel):
    participant_id: int
    ticket_id: int | None = None


class MessageCreate(BaseModel):
    body: str = Field(..., min_length=1, max_length=4000)


class MessageMuteRequest(BaseModel):
    minutes: int | None = Field(default=None, ge=0, le=10080)


class MessageContactResponse(MessageUserResponse):
    ticket_id: int | None = None
    reason: str | None = None
