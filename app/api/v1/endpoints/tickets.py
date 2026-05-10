from fastapi import APIRouter, Body, Depends, HTTPException, File, UploadFile
from sqlalchemy.orm import Session, joinedload
from typing import List
from datetime import datetime

from app.api.dependencies import get_db, get_current_user
from app.schemas.ticket import TicketAssign, TicketCancelRequest, TicketCreate, TicketFileResponse, TicketResponse, TicketUpdate
from app.services.ticket_service import TicketService
from app.models.user import User, UserRole
from app.schemas.history import HistoryResponse
from app.models.history import TicketHistory
from app.models.ticket import TicketPriority, TicketStatus

router = APIRouter()


def _ticket_response(ticket, current_user: User) -> TicketResponse:
    response = TicketResponse.model_validate(ticket)
    if (
        response.author
        and response.author_id != current_user.id
        and not response.show_contact_phone
    ):
        response.author.contact_phone = None
    if current_user.role == UserRole.RESIDENT and response.author_id != current_user.id:
        response.external_contact_phone = None
    return response


def _ticket_responses(tickets, current_user: User) -> list[TicketResponse]:
    return [_ticket_response(ticket, current_user) for ticket in tickets]


@router.post("/", response_model=TicketResponse)
def create_ticket(
        ticket_in: TicketCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    if current_user.role == UserRole.AUDITOR:
        raise HTTPException(status_code=403, detail="Auditors cannot create tickets")

    service = TicketService(db)
    return _ticket_response(service.create_ticket(ticket_in, user=current_user), current_user)


@router.get("/", response_model=List[TicketResponse])
def read_tickets(
        status: TicketStatus | None = None,
        house_id: int | None = None,
        executor_id: int | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        overdue_hours: int | None = None,
        priority: TicketPriority | None = None,
        limit: int = 100,
        skip: int = 0,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    service = TicketService(db)
    tickets = service.get_tickets(
        user=current_user,
        status=status,
        house_id=house_id,
        executor_id=executor_id,
        created_from=created_from,
        created_to=created_to,
        overdue_hours=overdue_hours,
        priority=priority,
        limit=limit,
        skip=skip,
    )
    return _ticket_responses(tickets, current_user)


@router.patch("/{ticket_id}/assign", response_model=TicketResponse)
def assign_ticket(
        ticket_id: int,
        assign_data: TicketAssign,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    service = TicketService(db)
    return _ticket_response(service.assign_executor(ticket_id, assign_data, current_user), current_user)


@router.post("/{ticket_id}/photos", response_model=TicketFileResponse)
def upload_ticket_photo(
        ticket_id: int,
        file: UploadFile = File(...),
        kind: str | None = None,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    service = TicketService(db)
    return service.upload_file(ticket_id, file, current_user, kind=kind)


@router.delete("/photos/{file_id}")
def delete_ticket_photo(
        file_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    service = TicketService(db)
    return service.delete_file(file_id, current_user)


@router.post("/{ticket_id}/cancel")
def cancel_ticket(
    ticket_id: int,
    payload: TicketCancelRequest | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = TicketService(db)
    return service.cancel_ticket(ticket_id, current_user, payload)


@router.get("/{ticket_id}", response_model=TicketResponse)
def read_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = TicketService(db)
    return _ticket_response(service.get_ticket_by_id(ticket_id, current_user), current_user)


@router.patch("/{ticket_id}/status", response_model=TicketResponse)
def update_ticket_status(
    ticket_id: int,
    status_data: TicketUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = TicketService(db)
    return _ticket_response(service.update_status(ticket_id, status_data, current_user), current_user)


@router.get("/{ticket_id}/history", response_model=List[HistoryResponse])
def read_ticket_history(
        ticket_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    service = TicketService(db)
    ticket = service.get_ticket_by_id(ticket_id, current_user)

    if current_user.role == UserRole.RESIDENT and ticket.author_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only ticket author can view history")

    history = (
        db.query(TicketHistory)
        .options(joinedload(TicketHistory.user))
        .filter(TicketHistory.ticket_id == ticket_id)
        .order_by(TicketHistory.created_at.desc())
        .all()
    )

    return history


@router.get("/history/all", response_model=List[HistoryResponse])
def read_all_history(
        ticket_id: int | None = None,
        user_id: int | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    if current_user.role not in [UserRole.ADMIN, UserRole.DISPATCHER, UserRole.AUDITOR]:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    q = db.query(TicketHistory).options(joinedload(TicketHistory.user))

    if ticket_id is not None:
        q = q.filter(TicketHistory.ticket_id == ticket_id)
    if user_id is not None:
        q = q.filter(TicketHistory.user_id == user_id)
    if created_from is not None:
        q = q.filter(TicketHistory.created_at >= created_from)
    if created_to is not None:
        q = q.filter(TicketHistory.created_at <= created_to)

    return q.order_by(TicketHistory.created_at.desc()).limit(1000).all()
