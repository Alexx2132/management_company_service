import csv
import io
from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.models.ticket import TicketPriority, TicketStatus
from app.models.user import User
from app.schemas.reporting import (
    AttentionTicketListResponse,
    ExecutorPerformanceResponse,
    ProblemCategoryResponse,
    ProblemHouseResponse,
    ReportingSummaryResponse,
)
from app.services.reporting_service import ReportingService

router = APIRouter()


@router.get("/summary", response_model=ReportingSummaryResponse)
def get_reporting_summary(
    date_from: date | None = None,
    date_to: date | None = None,
    house_id: int | None = None,
    category_id: int | None = None,
    executor_id: int | None = None,
    priority: TicketPriority | None = None,
    status: TicketStatus | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ReportingService(db)
    return service.get_summary(
        current_user=current_user,
        date_from=date_from,
        date_to=date_to,
        house_id=house_id,
        category_id=category_id,
        executor_id=executor_id,
        priority=priority,
        status=status,
    )


@router.get("/problem-houses", response_model=list[ProblemHouseResponse])
def get_problem_houses(
    date_from: date | None = None,
    date_to: date | None = None,
    category_id: int | None = None,
    executor_id: int | None = None,
    priority: TicketPriority | None = None,
    status: TicketStatus | None = None,
    top: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ReportingService(db)
    return service.get_problem_houses(
        current_user=current_user,
        date_from=date_from,
        date_to=date_to,
        category_id=category_id,
        executor_id=executor_id,
        priority=priority,
        status=status,
        top=top,
    )


@router.get("/problem-categories", response_model=list[ProblemCategoryResponse])
def get_problem_categories(
    date_from: date | None = None,
    date_to: date | None = None,
    house_id: int | None = None,
    executor_id: int | None = None,
    priority: TicketPriority | None = None,
    status: TicketStatus | None = None,
    top: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ReportingService(db)
    return service.get_problem_categories(
        current_user=current_user,
        date_from=date_from,
        date_to=date_to,
        house_id=house_id,
        executor_id=executor_id,
        priority=priority,
        status=status,
        top=top,
    )


@router.get("/executors/performance", response_model=list[ExecutorPerformanceResponse])
def get_executor_performance(
    date_from: date | None = None,
    date_to: date | None = None,
    house_id: int | None = None,
    category_id: int | None = None,
    executor_id: int | None = None,
    priority: TicketPriority | None = None,
    status: TicketStatus | None = None,
    top: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ReportingService(db)
    return service.get_executor_performance(
        current_user=current_user,
        date_from=date_from,
        date_to=date_to,
        house_id=house_id,
        category_id=category_id,
        executor_id=executor_id,
        priority=priority,
        status=status,
        top=top,
    )


@router.get("/attention-tickets", response_model=AttentionTicketListResponse)
def get_attention_tickets(
    date_from: date | None = None,
    date_to: date | None = None,
    house_id: int | None = None,
    category_id: int | None = None,
    executor_id: int | None = None,
    priority: TicketPriority | None = None,
    status: TicketStatus | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ReportingService(db)
    return service.get_attention_tickets(
        current_user=current_user,
        date_from=date_from,
        date_to=date_to,
        house_id=house_id,
        category_id=category_id,
        executor_id=executor_id,
        priority=priority,
        status=status,
        skip=skip,
        limit=limit,
    )


@router.get("/executors/performance/export.csv")
def export_executor_performance_csv(
    date_from: date | None = None,
    date_to: date | None = None,
    house_id: int | None = None,
    category_id: int | None = None,
    executor_id: int | None = None,
    priority: TicketPriority | None = None,
    status: TicketStatus | None = None,
    top: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ReportingService(db)
    rows = service.get_executor_performance(
        current_user=current_user,
        date_from=date_from,
        date_to=date_to,
        house_id=house_id,
        category_id=category_id,
        executor_id=executor_id,
        priority=priority,
        status=status,
        top=top,
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "executor_id",
        "full_name",
        "specialty",
        "assigned_tickets",
        "in_progress_tickets",
        "done_tickets",
        "closed_tickets",
        "overdue_tickets",
        "open_quality_complaints",
        "active_remarks",
        "avg_assignment_hours",
        "avg_completion_hours",
    ])

    for item in rows:
        writer.writerow([
            item.executor_id,
            item.full_name,
            item.specialty,
            item.assigned_tickets,
            item.in_progress_tickets,
            item.done_tickets,
            item.closed_tickets,
            item.overdue_tickets,
            item.open_quality_complaints,
            item.active_remarks,
            item.avg_assignment_hours,
            item.avg_completion_hours,
        ])

    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="executor_performance.csv"'},
    )


@router.get("/attention-tickets/export.csv")
def export_attention_tickets_csv(
    date_from: date | None = None,
    date_to: date | None = None,
    house_id: int | None = None,
    category_id: int | None = None,
    executor_id: int | None = None,
    priority: TicketPriority | None = None,
    status: TicketStatus | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=5000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ReportingService(db)
    payload = service.get_attention_tickets(
        current_user=current_user,
        date_from=date_from,
        date_to=date_to,
        house_id=house_id,
        category_id=category_id,
        executor_id=executor_id,
        priority=priority,
        status=status,
        skip=skip,
        limit=limit,
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "ticket_id",
        "title",
        "status",
        "priority",
        "house_address",
        "apartment",
        "category_name",
        "author_name",
        "executor_name",
        "created_at",
        "due_at",
        "planned_visit_at",
        "reopened_count",
        "first_response_overdue",
        "execution_overdue",
        "open_quality_complaints",
    ])

    for item in payload.items:
        writer.writerow([
            item.ticket_id,
            item.title,
            item.status,
            item.priority,
            item.house_address,
            item.apartment,
            item.category_name,
            item.author_name,
            item.executor_name,
            item.created_at,
            item.due_at,
            item.planned_visit_at,
            item.reopened_count,
            item.first_response_overdue,
            item.execution_overdue,
            item.open_quality_complaints,
        ])

    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="attention_tickets.csv"'},
    )