from datetime import date, datetime

from pydantic import BaseModel

from app.models.ticket import TicketPriority, TicketStatus


class ReportingSummaryResponse(BaseModel):
    date_from: date | None = None
    date_to: date | None = None

    total_tickets: int
    created_tickets: int
    assigned_tickets: int
    in_progress_tickets: int
    done_tickets: int
    closed_tickets: int
    canceled_tickets: int

    overdue_tickets: int
    first_response_overdue_tickets: int
    reopened_tickets: int
    emergency_tickets: int

    open_quality_complaints: int
    active_remarks: int

    avg_assignment_hours: float | None = None
    avg_completion_hours: float | None = None
    avg_close_hours: float | None = None


class ProblemHouseResponse(BaseModel):
    house_id: int | None = None
    address: str
    total_tickets: int
    open_tickets: int
    overdue_tickets: int
    first_response_overdue_tickets: int
    reopened_tickets: int
    emergency_tickets: int
    open_quality_complaints: int


class ProblemCategoryResponse(BaseModel):
    category_id: int | None = None
    category_name: str
    total_tickets: int
    open_tickets: int
    overdue_tickets: int
    first_response_overdue_tickets: int
    reopened_tickets: int
    emergency_tickets: int
    open_quality_complaints: int


class ExecutorPerformanceResponse(BaseModel):
    executor_id: int
    full_name: str
    specialty: str | None = None

    total_tickets: int
    assigned_tickets: int
    in_progress_tickets: int
    done_tickets: int
    closed_tickets: int
    overdue_tickets: int
    reopened_tickets: int

    open_quality_complaints: int
    active_remarks: int

    avg_assignment_hours: float | None = None
    avg_completion_hours: float | None = None


class AttentionTicketResponse(BaseModel):
    ticket_id: int
    title: str
    status: TicketStatus
    priority: TicketPriority
    created_at: datetime

    house_id: int | None = None
    house_address: str | None = None
    apartment: str | None = None

    category_id: int | None = None
    category_name: str | None = None

    author_id: int
    author_name: str | None = None

    executor_id: int | None = None
    executor_name: str | None = None

    first_response_due_at: datetime | None = None
    due_at: datetime | None = None
    planned_visit_at: datetime | None = None

    reopened_count: int
    reasons: list[str]


class AttentionTicketListResponse(BaseModel):
    total: int
    items: list[AttentionTicketResponse]