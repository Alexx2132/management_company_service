from pydantic import BaseModel
from datetime import datetime
from app.models.complaint import ComplaintType, ComplaintStatus


class ComplaintFileResponse(BaseModel):
    id: int
    file_path: str
    created_at: datetime

    class Config:
        from_attributes = True


class ComplaintCreate(BaseModel):
    complaint_type: ComplaintType
    description: str | None = None


class ComplaintResolve(BaseModel):
    status: ComplaintStatus
    resolution_comment: str | None = None


class TicketComplaintResponse(BaseModel):
    id: int
    ticket_id: int
    author_id: int
    complaint_type: ComplaintType
    description: str | None = None
    status: ComplaintStatus
    created_at: datetime

    resolver_id: int | None = None
    resolved_at: datetime | None = None
    resolution_comment: str | None = None

    files: list[ComplaintFileResponse] = []

    class Config:
        from_attributes = True
