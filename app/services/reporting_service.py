from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.models.category import Category
from app.models.location import House
from app.models.remark import Remark, RemarkStatus
from app.models.ticket import Ticket, TicketPriority, TicketStatus
from app.models.ticket_complaint import ComplaintStatus, ComplaintType, TicketComplaint
from app.models.user import User, UserRole
from app.schemas.reporting import (
    AttentionTicketListResponse,
    AttentionTicketResponse,
    ExecutorPerformanceResponse,
    ProblemCategoryResponse,
    ProblemHouseResponse,
    ReportingSummaryResponse,
)


SLA_FINAL_STATUSES = {
    TicketStatus.DONE,
    TicketStatus.CLOSED,
    TicketStatus.CANCELED,
}

VISIBLE_OPEN_STATUSES = {
    TicketStatus.CREATED,
    TicketStatus.ASSIGNED,
    TicketStatus.IN_PROGRESS,
    TicketStatus.DONE,
}

STAFF_ROLES = {UserRole.ADMIN, UserRole.ADMIN_ASSISTANT, UserRole.DISPATCHER, UserRole.AUDITOR}


@dataclass
class TicketReportFilters:
    date_from: date | None = None
    date_to: date | None = None
    house_id: int | None = None
    category_id: int | None = None
    executor_id: int | None = None
    priority: TicketPriority | None = None
    status: TicketStatus | None = None


class ReportingService:
    def __init__(self, db: Session):
        self.db = db

    def _ensure_staff(self, user: User) -> None:
        if user.role not in STAFF_ROLES:
            raise HTTPException(status_code=403, detail="Not enough permissions")

    def _resolve_period(self, date_from: date | None, date_to: date | None) -> tuple[datetime | None, datetime | None]:
        start_dt = datetime.combine(date_from, time.min) if date_from else None
        end_dt = datetime.combine(date_to, time.max) if date_to else None
        if start_dt and end_dt and start_dt > end_dt:
            raise HTTPException(status_code=400, detail="date_from must be less than or equal to date_to")
        return start_dt, end_dt

    def _apply_ticket_filters(self, query, filters: TicketReportFilters):
        start_dt, end_dt = self._resolve_period(filters.date_from, filters.date_to)

        if start_dt is not None:
            query = query.filter(Ticket.created_at >= start_dt)
        if end_dt is not None:
            query = query.filter(Ticket.created_at <= end_dt)
        if filters.house_id is not None:
            query = query.filter(Ticket.house_id == filters.house_id)
        if filters.category_id is not None:
            query = query.filter(Ticket.category_id == filters.category_id)
        if filters.executor_id is not None:
            query = query.filter(Ticket.executor_id == filters.executor_id)
        if filters.priority is not None:
            query = query.filter(Ticket.priority == filters.priority)
        if filters.status is not None:
            query = query.filter(Ticket.status == filters.status)

        return query

    def _get_tickets(self, filters: TicketReportFilters, eager: bool = False) -> list[Ticket]:
        query = self.db.query(Ticket)
        if eager:
            query = query.options(
                joinedload(Ticket.house),
                joinedload(Ticket.category),
                joinedload(Ticket.author),
                joinedload(Ticket.executor),
            )
        query = self._apply_ticket_filters(query, filters)
        return query.all()

    def _get_open_quality_complaints(self, filters: TicketReportFilters) -> list[TicketComplaint]:
        query = self.db.query(TicketComplaint).join(Ticket, Ticket.id == TicketComplaint.ticket_id).filter(
            TicketComplaint.complaint_type == ComplaintType.QUALITY,
            TicketComplaint.status == ComplaintStatus.OPEN,
        )
        query = self._apply_ticket_filters(query, filters)
        return query.all()

    def _avg_hours(self, values: list[float]) -> float | None:
        if not values:
            return None
        return round(sum(values) / len(values), 2)

    def _hours_between(self, start: datetime | None, end: datetime | None) -> float | None:
        if not start or not end:
            return None
        delta = end - start
        return round(delta.total_seconds() / 3600, 2)

    def _is_execution_overdue(self, ticket: Ticket, now: datetime) -> bool:
        return bool(
            ticket.due_at
            and ticket.due_at < now
            and ticket.status not in SLA_FINAL_STATUSES
        )

    def _is_first_response_overdue(self, ticket: Ticket, now: datetime) -> bool:
        return bool(
            ticket.first_response_due_at
            and ticket.first_response_due_at < now
            and ticket.executor_id is None
            and ticket.status not in SLA_FINAL_STATUSES
        )

    def _is_open_for_resident(self, ticket: Ticket) -> bool:
        return ticket.status in VISIBLE_OPEN_STATUSES

    def _build_complaint_maps(self, complaints: list[TicketComplaint]) -> tuple[dict[int, int], dict[int, int], dict[int, int], dict[int, int]]:
        by_ticket: dict[int, int] = defaultdict(int)
        by_house: dict[int, int] = defaultdict(int)
        by_category: dict[int, int] = defaultdict(int)
        by_executor: dict[int, int] = defaultdict(int)

        for complaint in complaints:
            ticket = complaint.ticket
            if not ticket:
                continue
            by_ticket[ticket.id] += 1
            if ticket.house_id is not None:
                by_house[ticket.house_id] += 1
            if ticket.category_id is not None:
                by_category[ticket.category_id] += 1
            if ticket.executor_id is not None:
                by_executor[ticket.executor_id] += 1

        return dict(by_ticket), dict(by_house), dict(by_category), dict(by_executor)

    def get_summary(
        self,
        current_user: User,
        date_from: date | None = None,
        date_to: date | None = None,
        house_id: int | None = None,
        category_id: int | None = None,
        executor_id: int | None = None,
        priority: TicketPriority | None = None,
        status: TicketStatus | None = None,
    ) -> ReportingSummaryResponse:
        self._ensure_staff(current_user)
        filters = TicketReportFilters(
            date_from=date_from,
            date_to=date_to,
            house_id=house_id,
            category_id=category_id,
            executor_id=executor_id,
            priority=priority,
            status=status,
        )
        tickets = self._get_tickets(filters)
        complaints = self._get_open_quality_complaints(filters)
        now = datetime.utcnow()

        avg_assignment_values: list[float] = []
        avg_completion_values: list[float] = []
        avg_close_values: list[float] = []

        for ticket in tickets:
            assignment_hours = self._hours_between(ticket.created_at, ticket.assigned_at)
            if assignment_hours is not None:
                avg_assignment_values.append(assignment_hours)

            completion_point = ticket.done_at or ticket.closed_at
            completion_hours = self._hours_between(ticket.created_at, completion_point)
            if completion_hours is not None:
                avg_completion_values.append(completion_hours)

            close_hours = self._hours_between(ticket.created_at, ticket.closed_at)
            if close_hours is not None:
                avg_close_values.append(close_hours)

        active_remarks_query = self.db.query(Remark).filter(Remark.status == RemarkStatus.ACTIVE)
        if executor_id is not None:
            active_remarks_query = active_remarks_query.filter(Remark.executor_id == executor_id)
        active_remarks = active_remarks_query.count()

        return ReportingSummaryResponse(
            date_from=date_from,
            date_to=date_to,
            total_tickets=len(tickets),
            created_tickets=sum(1 for t in tickets if t.status == TicketStatus.CREATED),
            assigned_tickets=sum(1 for t in tickets if t.status == TicketStatus.ASSIGNED),
            in_progress_tickets=sum(1 for t in tickets if t.status == TicketStatus.IN_PROGRESS),
            done_tickets=sum(1 for t in tickets if t.status == TicketStatus.DONE),
            closed_tickets=sum(1 for t in tickets if t.status == TicketStatus.CLOSED),
            canceled_tickets=sum(1 for t in tickets if t.status == TicketStatus.CANCELED),
            overdue_tickets=sum(1 for t in tickets if self._is_execution_overdue(t, now)),
            first_response_overdue_tickets=sum(1 for t in tickets if self._is_first_response_overdue(t, now)),
            reopened_tickets=sum(1 for t in tickets if (t.reopened_count or 0) > 0),
            emergency_tickets=sum(1 for t in tickets if t.priority == TicketPriority.EMERGENCY),
            open_quality_complaints=len(complaints),
            active_remarks=active_remarks,
            avg_assignment_hours=self._avg_hours(avg_assignment_values),
            avg_completion_hours=self._avg_hours(avg_completion_values),
            avg_close_hours=self._avg_hours(avg_close_values),
        )

    def get_problem_houses(
        self,
        current_user: User,
        date_from: date | None = None,
        date_to: date | None = None,
        category_id: int | None = None,
        executor_id: int | None = None,
        priority: TicketPriority | None = None,
        status: TicketStatus | None = None,
        top: int = 10,
    ) -> list[ProblemHouseResponse]:
        self._ensure_staff(current_user)
        filters = TicketReportFilters(
            date_from=date_from,
            date_to=date_to,
            category_id=category_id,
            executor_id=executor_id,
            priority=priority,
            status=status,
        )
        tickets = self._get_tickets(filters, eager=True)
        complaints = self._get_open_quality_complaints(filters)
        _, complaints_by_house, _, _ = self._build_complaint_maps(complaints)
        now = datetime.utcnow()

        grouped: dict[int | None, dict] = {}
        for ticket in tickets:
            key = ticket.house_id
            if key not in grouped:
                grouped[key] = {
                    "address": ticket.house.address if ticket.house else "Без привязки к дому",
                    "total_tickets": 0,
                    "open_tickets": 0,
                    "overdue_tickets": 0,
                    "first_response_overdue_tickets": 0,
                    "reopened_tickets": 0,
                    "emergency_tickets": 0,
                }

            row = grouped[key]
            row["total_tickets"] += 1
            row["open_tickets"] += int(self._is_open_for_resident(ticket))
            row["overdue_tickets"] += int(self._is_execution_overdue(ticket, now))
            row["first_response_overdue_tickets"] += int(self._is_first_response_overdue(ticket, now))
            row["reopened_tickets"] += int((ticket.reopened_count or 0) > 0)
            row["emergency_tickets"] += int(ticket.priority == TicketPriority.EMERGENCY)

        result: list[ProblemHouseResponse] = []
        for house_key, data in grouped.items():
            result.append(
                ProblemHouseResponse(
                    house_id=house_key,
                    address=data["address"],
                    total_tickets=data["total_tickets"],
                    open_tickets=data["open_tickets"],
                    overdue_tickets=data["overdue_tickets"],
                    first_response_overdue_tickets=data["first_response_overdue_tickets"],
                    reopened_tickets=data["reopened_tickets"],
                    emergency_tickets=data["emergency_tickets"],
                    open_quality_complaints=complaints_by_house.get(house_key, 0) if house_key is not None else 0,
                )
            )

        result.sort(
            key=lambda x: (
                x.overdue_tickets,
                x.open_quality_complaints,
                x.first_response_overdue_tickets,
                x.reopened_tickets,
                x.total_tickets,
            ),
            reverse=True,
        )
        return result[:top]

    def get_problem_categories(
        self,
        current_user: User,
        date_from: date | None = None,
        date_to: date | None = None,
        house_id: int | None = None,
        executor_id: int | None = None,
        priority: TicketPriority | None = None,
        status: TicketStatus | None = None,
        top: int = 10,
    ) -> list[ProblemCategoryResponse]:
        self._ensure_staff(current_user)
        filters = TicketReportFilters(
            date_from=date_from,
            date_to=date_to,
            house_id=house_id,
            executor_id=executor_id,
            priority=priority,
            status=status,
        )
        tickets = self._get_tickets(filters, eager=True)
        complaints = self._get_open_quality_complaints(filters)
        _, _, complaints_by_category, _ = self._build_complaint_maps(complaints)
        now = datetime.utcnow()

        grouped: dict[int | None, dict] = {}
        for ticket in tickets:
            key = ticket.category_id
            if key not in grouped:
                grouped[key] = {
                    "category_name": ticket.category.name if ticket.category else "Без категории",
                    "total_tickets": 0,
                    "open_tickets": 0,
                    "overdue_tickets": 0,
                    "first_response_overdue_tickets": 0,
                    "reopened_tickets": 0,
                    "emergency_tickets": 0,
                }

            row = grouped[key]
            row["total_tickets"] += 1
            row["open_tickets"] += int(self._is_open_for_resident(ticket))
            row["overdue_tickets"] += int(self._is_execution_overdue(ticket, now))
            row["first_response_overdue_tickets"] += int(self._is_first_response_overdue(ticket, now))
            row["reopened_tickets"] += int((ticket.reopened_count or 0) > 0)
            row["emergency_tickets"] += int(ticket.priority == TicketPriority.EMERGENCY)

        result: list[ProblemCategoryResponse] = []
        for category_key, data in grouped.items():
            result.append(
                ProblemCategoryResponse(
                    category_id=category_key,
                    category_name=data["category_name"],
                    total_tickets=data["total_tickets"],
                    open_tickets=data["open_tickets"],
                    overdue_tickets=data["overdue_tickets"],
                    first_response_overdue_tickets=data["first_response_overdue_tickets"],
                    reopened_tickets=data["reopened_tickets"],
                    emergency_tickets=data["emergency_tickets"],
                    open_quality_complaints=complaints_by_category.get(category_key, 0) if category_key is not None else 0,
                )
            )

        result.sort(
            key=lambda x: (
                x.overdue_tickets,
                x.open_quality_complaints,
                x.first_response_overdue_tickets,
                x.reopened_tickets,
                x.total_tickets,
            ),
            reverse=True,
        )
        return result[:top]

    def get_executor_performance(
        self,
        current_user: User,
        date_from: date | None = None,
        date_to: date | None = None,
        house_id: int | None = None,
        category_id: int | None = None,
        executor_id: int | None = None,
        priority: TicketPriority | None = None,
        status: TicketStatus | None = None,
        top: int = 50,
    ) -> list[ExecutorPerformanceResponse]:
        self._ensure_staff(current_user)
        filters = TicketReportFilters(
            date_from=date_from,
            date_to=date_to,
            house_id=house_id,
            category_id=category_id,
            executor_id=executor_id,
            priority=priority,
            status=status,
        )
        tickets = [ticket for ticket in self._get_tickets(filters, eager=True) if ticket.executor_id is not None]
        complaints = self._get_open_quality_complaints(filters)
        _, _, _, complaints_by_executor = self._build_complaint_maps(complaints)
        now = datetime.utcnow()

        executors_query = self.db.query(User).filter(User.role == UserRole.EXECUTOR)
        if executor_id is not None:
            executors_query = executors_query.filter(User.id == executor_id)
        executors = executors_query.order_by(User.full_name.asc()).all()

        tickets_by_executor: dict[int, list[Ticket]] = defaultdict(list)
        for ticket in tickets:
            if ticket.executor_id is not None:
                tickets_by_executor[ticket.executor_id].append(ticket)

        active_remarks_rows = self.db.query(Remark).filter(Remark.status == RemarkStatus.ACTIVE).all()
        active_remarks_by_executor: dict[int, int] = defaultdict(int)
        for remark in active_remarks_rows:
            active_remarks_by_executor[remark.executor_id] += 1

        result: list[ExecutorPerformanceResponse] = []
        for executor in executors:
            executor_tickets = tickets_by_executor.get(executor.id, [])
            avg_assignment_values: list[float] = []
            avg_completion_values: list[float] = []

            for ticket in executor_tickets:
                assignment_hours = self._hours_between(ticket.created_at, ticket.assigned_at)
                if assignment_hours is not None:
                    avg_assignment_values.append(assignment_hours)

                completion_hours = self._hours_between(ticket.created_at, ticket.done_at or ticket.closed_at)
                if completion_hours is not None:
                    avg_completion_values.append(completion_hours)

            result.append(
                ExecutorPerformanceResponse(
                    executor_id=executor.id,
                    full_name=executor.full_name,
                    specialty=executor.specialty,
                    total_tickets=len(executor_tickets),
                    assigned_tickets=sum(1 for t in executor_tickets if t.status == TicketStatus.ASSIGNED),
                    in_progress_tickets=sum(1 for t in executor_tickets if t.status == TicketStatus.IN_PROGRESS),
                    done_tickets=sum(1 for t in executor_tickets if t.status == TicketStatus.DONE),
                    closed_tickets=sum(1 for t in executor_tickets if t.status == TicketStatus.CLOSED),
                    overdue_tickets=sum(1 for t in executor_tickets if self._is_execution_overdue(t, now)),
                    reopened_tickets=sum(1 for t in executor_tickets if (t.reopened_count or 0) > 0),
                    open_quality_complaints=complaints_by_executor.get(executor.id, 0),
                    active_remarks=active_remarks_by_executor.get(executor.id, 0),
                    avg_assignment_hours=self._avg_hours(avg_assignment_values),
                    avg_completion_hours=self._avg_hours(avg_completion_values),
                )
            )

        result.sort(
            key=lambda x: (
                x.overdue_tickets,
                x.open_quality_complaints,
                x.reopened_tickets,
                x.total_tickets,
            ),
            reverse=True,
        )
        return result[:top]

    def get_attention_tickets(
        self,
        current_user: User,
        date_from: date | None = None,
        date_to: date | None = None,
        house_id: int | None = None,
        category_id: int | None = None,
        executor_id: int | None = None,
        priority: TicketPriority | None = None,
        status: TicketStatus | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> AttentionTicketListResponse:
        self._ensure_staff(current_user)
        filters = TicketReportFilters(
            date_from=date_from,
            date_to=date_to,
            house_id=house_id,
            category_id=category_id,
            executor_id=executor_id,
            priority=priority,
            status=status,
        )
        tickets = self._get_tickets(filters, eager=True)
        complaints = self._get_open_quality_complaints(filters)
        complaints_by_ticket, _, _, _ = self._build_complaint_maps(complaints)
        now = datetime.utcnow()

        attention_items: list[AttentionTicketResponse] = []
        for ticket in tickets:
            reasons: list[str] = []

            if ticket.status == TicketStatus.CREATED and ticket.executor_id is None:
                reasons.append("unassigned")
            if self._is_first_response_overdue(ticket, now):
                reasons.append("first_response_overdue")
            if self._is_execution_overdue(ticket, now):
                reasons.append("execution_overdue")
            if (ticket.reopened_count or 0) > 0:
                reasons.append("reopened_after_quality_complaint")
            if complaints_by_ticket.get(ticket.id, 0) > 0:
                reasons.append("open_quality_complaint")
            if ticket.priority == TicketPriority.EMERGENCY:
                reasons.append("emergency")
            if ticket.status == TicketStatus.DONE:
                reasons.append("done_waiting_resident_close")

            if not reasons:
                continue

            attention_items.append(
                AttentionTicketResponse(
                    ticket_id=ticket.id,
                    title=ticket.title,
                    status=ticket.status,
                    priority=ticket.priority,
                    created_at=ticket.created_at,
                    house_id=ticket.house_id,
                    house_address=ticket.house.address if ticket.house else None,
                    apartment=ticket.apartment,
                    category_id=ticket.category_id,
                    category_name=ticket.category.name if ticket.category else None,
                    author_id=ticket.author_id,
                    author_name=ticket.author.full_name if ticket.author else None,
                    executor_id=ticket.executor_id,
                    executor_name=ticket.executor.full_name if ticket.executor else None,
                    first_response_due_at=ticket.first_response_due_at,
                    due_at=ticket.due_at,
                    planned_visit_at=ticket.planned_visit_at,
                    reopened_count=ticket.reopened_count or 0,
                    reasons=reasons,
                )
            )

        def sort_key(item: AttentionTicketResponse):
            return (
                "emergency" in item.reasons,
                "execution_overdue" in item.reasons,
                "first_response_overdue" in item.reasons,
                "open_quality_complaint" in item.reasons,
                item.created_at,
            )

        attention_items.sort(key=sort_key, reverse=True)
        total = len(attention_items)
        items = attention_items[skip : skip + limit]
        return AttentionTicketListResponse(total=total, items=items)
