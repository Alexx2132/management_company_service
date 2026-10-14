from sqlalchemy.ext.asyncio import AsyncSession
from app.db.operations import run_db

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_current_user
from app.models.user import User, UserRole
from app.models.complaint import ComplaintStatus
from app.schemas.complaint import TicketComplaintResponse, ComplaintResolve
from app.schemas.ticket_complaint import TicketComplaintResolve
from app.services.ticket_complaint_service import TicketComplaintService

router = APIRouter()


def _ensure_staff(user: User) -> None:
    if user.role not in [UserRole.ADMIN, UserRole.DISPATCHER, UserRole.AUDITOR]:
        raise HTTPException(status_code=403, detail="Not enough permissions")


@router.get("/", response_model=list[TicketComplaintResponse])
async def list_complaints(
        status: ComplaintStatus | None = None,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    def operation(db: Session):
        """Список всех жалоб (для диспетчера/аудитора/админа)."""
        _ensure_staff(current_user)

        return TicketComplaintService(db).list_complaints(current_user, status=status, limit=500)

    return await run_db(db, operation, list[TicketComplaintResponse])


@router.patch("/{complaint_id}/resolve", response_model=TicketComplaintResponse)
async def resolve_complaint(
        complaint_id: int,
        data: ComplaintResolve,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    def operation(db: Session):
        """Закрыть/отклонить жалобу (диспетчер/админ/аудитор)."""
        _ensure_staff(current_user)

        return TicketComplaintService(db).resolve(
            complaint_id, TicketComplaintResolve(**data.model_dump()), current_user,
        )

    return await run_db(db, operation, TicketComplaintResponse)
