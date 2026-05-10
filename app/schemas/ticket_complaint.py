from datetime import datetime
from pydantic import BaseModel

from app.models.ticket_complaint import ComplaintType, ComplaintStatus


class ComplaintFileResponse(BaseModel):
    id: int
    file_path: str
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class ComplaintCommentCreate(BaseModel):
    message: str
    visibility: str | None = None


class ComplaintCommentResponse(BaseModel):
    id: int
    complaint_id: int
    author_id: int
    author_name: str | None = None
    author_role: str | None = None
    message: str
    visibility: str = "public"
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class TicketComplaintCreate(BaseModel):
    ticket_id: int
    complaint_type: ComplaintType
    description: str | None = None
    parent_complaint_id: int | None = None


class TicketComplaintResolve(BaseModel):
    status: ComplaintStatus
    resolution_comment: str | None = None
    resident_resolution_comment: str | None = None
    staff_comment: str | None = None


class TicketComplaintResponse(BaseModel):
    id: int
    ticket_id: int
    author_id: int
    author_name: str | None = None
    complaint_type: ComplaintType
    description: str | None = None
    parent_complaint_id: int | None = None
    status: ComplaintStatus
    created_at: datetime | None = None

    resolver_id: int | None = None
    resolver_name: str | None = None
    resolver_role: str | None = None
    resolved_at: datetime | None = None
    resolution_comment: str | None = None

    files: list[ComplaintFileResponse] = []
    comments: list[ComplaintCommentResponse] = []

    class Config:
        from_attributes = True
