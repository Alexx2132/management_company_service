from pydantic import BaseModel
from datetime import datetime


class HistoryResponse(BaseModel):
    id: int
    ticket_id: int
    user_id: int
    user_name: str | None = None
    user_role: str | None = None
    old_status: str | None = None
    new_status: str
    comment: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True
