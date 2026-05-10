from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_current_user
from app.models.user import User
from app.schemas.ticket_comment import TicketCommentCreate, TicketCommentResponse
from app.services.ticket_comment_service import TicketCommentService

router = APIRouter()


@router.get("/{ticket_id}/comments", response_model=list[TicketCommentResponse])
def list_ticket_comments(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = TicketCommentService(db)
    return service.list_comments(ticket_id, current_user)


@router.post("/{ticket_id}/comments", response_model=TicketCommentResponse)
def create_ticket_comment(
    ticket_id: int,
    data: TicketCommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = TicketCommentService(db)
    return service.create_comment(ticket_id, data.message, data.is_internal, current_user)