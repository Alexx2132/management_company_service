from pydantic import BaseModel
from datetime import datetime
from app.models.ticket import TicketStatus


# --- Схемы для файлов ---
class TicketFileResponse(BaseModel):
    id: int
    file_path: str

    class Config:
        from_attributes = True


# --- Схемы для заявок ---

class TicketBase(BaseModel):
    title: str
    description: str | None = None
    house_id: int
    apartment: str | None = None
    category_id: int | None = None


class TicketCreate(TicketBase):
    created_for_user_id: int | None = None


class TicketUpdate(BaseModel):
    status: TicketStatus | None = None
    executor_id: int | None = None
    description: str | None = None
    comment: str | None = None


class TicketAssign(BaseModel):
    executor_id: int


class TicketResponse(TicketBase):
    id: int
    status: TicketStatus
    author_id: int
    executor_id: int | None = None
    created_at: datetime

    # Файлы можно оставить, они не вызывают рекурсию (в TicketFileResponse нет ссылки на Ticket)
    files: list[TicketFileResponse] = []

    class Config:
        from_attributes = True
