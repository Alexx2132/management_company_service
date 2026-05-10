from datetime import date, datetime, time

from pydantic import BaseModel, Field
from app.schemas.location import HouseResponse
from app.schemas.remark import RemarkResponse
from app.schemas.ticket import TicketResponse


class SpecialtyBase(BaseModel):
    code: str
    name: str


class SpecialtyCreate(SpecialtyBase):
    pass


class SpecialtyResponse(SpecialtyBase):
    id: int

    class Config:
        from_attributes = True


class ExecutorSpecialtyAssign(BaseModel):
    specialty_id: int
    is_primary: bool = False


class ExecutorProfileBase(BaseModel):
    first_name: str
    last_name: str
    middle_name: str | None = None
    phone: str | None = None
    notes: str | None = None
    house_id: int | None = None
    is_active: bool = True


class ExecutorCreateRequest(ExecutorProfileBase):
    login: str
    password: str
    specialty_ids: list[int] = Field(default_factory=list)
    primary_specialty_id: int | None = None


class ExecutorUpdateRequest(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    middle_name: str | None = None
    phone: str | None = None
    notes: str | None = None
    house_id: int | None = None
    is_active: bool | None = None
    specialty_ids: list[int] | None = None
    primary_specialty_id: int | None = None


class ExecutorUserShort(BaseModel):
    id: int
    login: str
    contact_phone: str | None = None

    class Config:
        from_attributes = True


class ExecutorSpecialtyResponse(BaseModel):
    id: int
    specialty_id: int
    is_primary: bool
    specialty: SpecialtyResponse

    class Config:
        from_attributes = True


class ExecutorWorkScheduleCreate(BaseModel):
    weekday: int = Field(..., ge=0, le=6)
    work_start: time
    work_end: time
    is_active: bool = True


class ExecutorWorkScheduleResponse(ExecutorWorkScheduleCreate):
    id: int

    class Config:
        from_attributes = True


class ExecutorDayOffCreate(BaseModel):
    off_date: date
    reason: str | None = None
    is_active: bool = True


class ExecutorDayOffResponse(ExecutorDayOffCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class ExecutorProfileResponse(ExecutorProfileBase):
    id: int
    user_id: int
    created_at: datetime
    user: ExecutorUserShort
    house: HouseResponse | None = None
    specialties: list[ExecutorSpecialtyResponse] = []
    work_schedules: list[ExecutorWorkScheduleResponse] = []
    days_off: list[ExecutorDayOffResponse] = []

    class Config:
        from_attributes = True


class ExecutorAvailabilityResponse(BaseModel):
    executor_id: int
    user_id: int
    full_name: str
    contact_phone: str | None = None
    house_id: int | None = None
    primary_specialty: str | None = None
    notes: str | None = None

    working_today: bool
    has_day_off_today: bool

    assigned_count: int
    in_progress_count: int
    active_total_count: int

    class Config:
        from_attributes = True


class ExecutorAnalyticsResponse(BaseModel):
    profile: ExecutorProfileResponse
    completed_tickets: list[TicketResponse] = []
    active_remarks: list[RemarkResponse] = []
    archived_remarks: list[RemarkResponse] = []
