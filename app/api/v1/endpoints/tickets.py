from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from sqlalchemy.orm import Session
from typing import List
from app.models.ticket import TicketStatus
from app.api.dependencies import get_db, get_current_user
from app.schemas.ticket import TicketCreate, TicketResponse, TicketAssign, TicketFileResponse, TicketUpdate
from app.services.ticket_service import TicketService
from app.models.user import User, UserRole

router = APIRouter()

@router.post("/", response_model=TicketResponse)
def create_ticket(
        ticket_in: TicketCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Создать новую заявку"""
    # Защита от Аудитора
    if current_user.role == UserRole.AUDITOR:
        raise HTTPException(status_code=403, detail="Auditors cannot create tickets")

    service = TicketService(db)
    return service.create_ticket(ticket_in, user=current_user)

@router.get("/", response_model=List[TicketResponse])
def read_tickets(
        # --- ВОТ ЭТИХ СТРОК У ВАС НЕ ХВАТАЕТ ---
        status: TicketStatus | None = None,
        house_id: int | None = None,
        executor_id: int | None = None,
        # ---------------------------------------
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Получить список заявок (с фильтрацией)"""
    service = TicketService(db)

    # И здесь мы должны передать эти параметры в сервис!
    return service.get_tickets(
        user=current_user,
        status=status,
        house_id=house_id,
        executor_id=executor_id
    )

@router.patch("/{ticket_id}/assign", response_model=TicketResponse)
def assign_ticket(
        ticket_id: int,
        assign_data: TicketAssign,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Назначить исполнителя"""
    service = TicketService(db)
    return service.assign_ticket(ticket_id, assign_data, current_user)

@router.post("/{ticket_id}/photos", response_model=TicketFileResponse)
def upload_ticket_photo(
        ticket_id: int,
        file: UploadFile = File(...),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Загрузить фото"""
    service = TicketService(db)
    return service.upload_file(ticket_id, file, current_user)

# --- ВОТ ЭТОТ МЕТОД У ВАС ПРОПАЛ ---
@router.delete("/photos/{file_id}")
def delete_ticket_photo(
        file_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Удалить фото"""
    service = TicketService(db)
    return service.delete_file(file_id, current_user)
# -----------------------------------

@router.post("/{ticket_id}/cancel")
def cancel_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Отменить заявку"""
    service = TicketService(db)
    return service.cancel_ticket(ticket_id, current_user)

@router.get("/", response_model=List[TicketResponse])
def read_tickets(
    status: TicketStatus | None = None,
    house_id: int | None = None,
    executor_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получить список заявок.
    Поддерживает фильтрацию для персонала.
    """
    service = TicketService(db)
    return service.get_tickets(
        current_user,
        status=status,
        house_id=house_id,
        executor_id=executor_id
    )

@router.patch("/{ticket_id}/status", response_model=TicketResponse)
def update_ticket_status(
    ticket_id: int,
    status_data: TicketUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Сменить статус заявки.
    - Исполнитель: IN_PROGRESS, DONE (нужно фото), CREATED (отказ + коммент).
    - Жилец: CLOSED.
    """
    service = TicketService(db)
    return service.update_status(ticket_id, status_data, current_user)