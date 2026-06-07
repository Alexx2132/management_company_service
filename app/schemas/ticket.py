from datetime import datetime

from pydantic import BaseModel

from app.models.ticket import TicketPriority, TicketStatus
from app.schemas.location import ApartmentResponse


class UserShortResponse(BaseModel):
    id: int
    full_name: str
    login: str | None = None
    phone: str | None = None
    contact_phone: str | None = None
    role: str | None = None
    house_id: int | None = None
    apartment_id: int | None = None
    specialty: str | None = None
    banned_until: datetime | None = None

    class Config:
        from_attributes = True


class HouseShortResponse(BaseModel):
    id: int
    address: str
    city: str | None = None

    class Config:
        from_attributes = True


class CategoryShortResponse(BaseModel):
    id: int
    name: str
    category_type: str = "problem"

    class Config:
        from_attributes = True


class TicketFileResponse(BaseModel):
    id: int
    file_path: str
    kind: str | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class TicketBase(BaseModel):
    title: str
    description: str | None = None
    house_id: int | None = None
    apartment_id: int | None = None
    apartment: str | None = None
    category_id: int | None = None
    place_category_id: int | None = None
    priority: TicketPriority = TicketPriority.NORMAL
    show_contact_phone: bool = False
    external_contact_phone: str | None = None


class TicketCreate(TicketBase):
    created_for_user_id: int | None = None


class TicketUpdate(BaseModel):
    status: TicketStatus | None = None
    executor_id: int | None = None
    description: str | None = None
    comment: str | None = None


class TicketAssign(BaseModel):
    executor_id: int | None = None
    executor_profile_id: int | None = None


class TicketCancelRequest(BaseModel):
    reason: str | None = None


class TicketResponse(TicketBase):
    id: int
    status: TicketStatus
    status_label: str | None = None
    author_id: int
    executor_id: int | None = None
    created_at: datetime
    is_external_request: bool = False

    house: HouseShortResponse | None = None
    apartment_ref: ApartmentResponse | None = None
    category: CategoryShortResponse | None = None
    place_category: CategoryShortResponse | None = None
    author: UserShortResponse | None = None
    executor: UserShortResponse | None = None

    result_comment: str | None = None
    files: list[TicketFileResponse] = []

    class Config:
        from_attributes = True
