from datetime import datetime

from pydantic import BaseModel, Field

from app.models.ticket import TicketPriority


class OperationsDashboardResponse(BaseModel):
    total_tickets: int
    unassigned_tickets: int
    assigned_tickets: int
    in_progress_tickets: int
    done_waiting_close_tickets: int
    open_quality_complaints: int
    active_remarks: int


class ExecutorLoadResponse(BaseModel):
    executor_id: int
    full_name: str
    specialty: str | None = None
    assigned_tickets: int
    in_progress_tickets: int
    done_tickets: int
    active_remarks: int
    quality_complaints_on_tickets: int


class ExecutorRecommendationResponse(BaseModel):
    executor_id: int
    full_name: str
    specialty: str | None = None
    assigned_tickets: int
    in_progress_tickets: int
    active_remarks: int
    open_quality_complaints: int
    active_score: float
    matches_category: bool
    recommendation_reason: str


class BulkTicketSkipResponse(BaseModel):
    ticket_id: int
    reason: str


class BulkTicketOperationResponse(BaseModel):
    requested_count: int
    updated_count: int
    updated_ticket_ids: list[int]
    missing_ticket_ids: list[int]
    skipped: list[BulkTicketSkipResponse]
    message: str


class BulkAssignTicketsRequest(BaseModel):
    ticket_ids: list[int] = Field(..., min_length=1)
    executor_id: int
    planned_visit_at: datetime | None = None


class BulkPriorityUpdateRequest(BaseModel):
    ticket_ids: list[int] = Field(..., min_length=1)
    priority: TicketPriority
    recalculate_due_dates: bool = True


class BulkPlanVisitRequest(BaseModel):
    ticket_ids: list[int] = Field(..., min_length=1)
    planned_visit_at: datetime