from datetime import datetime

from pydantic import BaseModel


class TicketCommentCreate(BaseModel):
    message: str
    is_internal: bool = False


class TicketCommentResponse(BaseModel):
    id: int
    ticket_id: int
    author_id: int
    author_name: str | None = None
    message: str
    is_internal: bool
    created_at: datetime

    class Config:
        from_attributes = True