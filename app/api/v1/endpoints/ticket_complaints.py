from typing import Annotated, List

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_current_user
from app.models.user import User
from app.models.ticket_complaint import ComplaintStatus, ComplaintType
from app.schemas.ticket_complaint import (
    ComplaintCommentCreate,
    ComplaintCommentResponse,
    TicketComplaintCreate,
    TicketComplaintResponse,
    ComplaintFileResponse,
    TicketComplaintResolve,
)
from app.services.ticket_complaint_service import TicketComplaintService

router = APIRouter()


@router.post("/", response_model=TicketComplaintResponse)
def create_ticket_complaint(
    data: TicketComplaintCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = TicketComplaintService(db)
    return service.create_complaint(data, current_user)


@router.get("/", response_model=List[TicketComplaintResponse])
def list_ticket_complaints(
    status: ComplaintStatus | None = None,
    complaint_type: ComplaintType | None = None,
    type: Annotated[ComplaintType | None, Query(alias="type")] = None,
    ticket_id: int | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = TicketComplaintService(db)
    return service.list_complaints(
        user=current_user,
        status=status,
        complaint_type=complaint_type or type,
        ticket_id=ticket_id,
        skip=skip,
        limit=limit
    )


@router.get("/{complaint_id}", response_model=TicketComplaintResponse)
def read_ticket_complaint(
    complaint_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = TicketComplaintService(db)
    return service.get_by_id(complaint_id, current_user)


@router.post("/{complaint_id}/photos", response_model=ComplaintFileResponse)
def upload_complaint_photo(
    complaint_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = TicketComplaintService(db)
    return service.add_photo(complaint_id, file, current_user)


@router.get("/{complaint_id}/comments", response_model=List[ComplaintCommentResponse])
def list_complaint_comments(
    complaint_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = TicketComplaintService(db)
    return service.list_comments(complaint_id, current_user)


@router.post("/{complaint_id}/comments", response_model=ComplaintCommentResponse)
def create_complaint_comment(
    complaint_id: int,
    data: ComplaintCommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = TicketComplaintService(db)
    return service.create_comment(complaint_id, data.message, current_user, data.visibility)


@router.patch("/{complaint_id}/resolve", response_model=TicketComplaintResponse)
def resolve_complaint(
    complaint_id: int,
    data: TicketComplaintResolve,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = TicketComplaintService(db)
    return service.resolve(complaint_id, data, current_user)


@router.post("/{complaint_id}/cancel", response_model=TicketComplaintResponse)
def cancel_complaint(
    complaint_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = TicketComplaintService(db)
    return service.cancel_complaint(complaint_id, current_user)
