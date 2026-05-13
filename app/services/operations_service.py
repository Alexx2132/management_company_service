from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.remark import Remark, RemarkStatus
from app.models.ticket import Ticket, TicketPriority, TicketStatus
from app.models.ticket_complaint import ComplaintStatus, ComplaintType, TicketComplaint
from app.models.user import User, UserRole
from app.schemas.operations import (
    BulkAssignTicketsRequest,
    BulkPlanVisitRequest,
    BulkPriorityUpdateRequest,
    BulkTicketOperationResponse,
    BulkTicketSkipResponse,
    ExecutorLoadResponse,
    ExecutorRecommendationResponse,
    OperationsDashboardResponse,
)
from app.services.notification_service import NotificationService


FINAL_STATUSES = {TicketStatus.DONE, TicketStatus.CLOSED, TicketStatus.CANCELED}
VIEW_ROLES = {UserRole.ADMIN, UserRole.ADMIN_ASSISTANT, UserRole.DISPATCHER, UserRole.AUDITOR}
MANAGE_ROLES = {UserRole.ADMIN, UserRole.DISPATCHER}


class OperationsService:
    def __init__(self, db: Session):
        self.db = db

    def _ensure_view_permissions(self, user: User) -> None:
        if user.role not in VIEW_ROLES:
            raise HTTPException(status_code=403, detail="Not enough permissions")

    def _ensure_manage_permissions(self, user: User) -> None:
        if user.role not in MANAGE_ROLES:
            raise HTTPException(status_code=403, detail="Not enough permissions")

    def _has_ticket_attr(self, attr_name: str) -> bool:
        return hasattr(Ticket, attr_name)

    def _priority_deadlines(self, created_at: datetime, priority: TicketPriority) -> tuple[datetime, datetime]:
        emergency_member = getattr(TicketPriority, "EMERGENCY", None)
        urgent_member = getattr(TicketPriority, "URGENT", None)

        if priority == TicketPriority.LOW:
            return created_at + timedelta(hours=24), created_at + timedelta(days=5)

        if priority == TicketPriority.HIGH:
            return created_at + timedelta(hours=2), created_at + timedelta(hours=24)

        if emergency_member is not None and priority == emergency_member:
            return created_at + timedelta(minutes=30), created_at + timedelta(hours=4)

        if urgent_member is not None and priority == urgent_member:
            return created_at + timedelta(minutes=30), created_at + timedelta(hours=4)

        return created_at + timedelta(hours=4), created_at + timedelta(hours=72)

    def _build_skip(self, ticket_id: int, reason: str) -> BulkTicketSkipResponse:
        return BulkTicketSkipResponse(ticket_id=ticket_id, reason=reason)

    def _deduplicate_ids(self, ticket_ids: list[int]) -> list[int]:
        seen: set[int] = set()
        result: list[int] = []
        for ticket_id in ticket_ids:
            if ticket_id not in seen:
                seen.add(ticket_id)
                result.append(ticket_id)
        return result

    def get_dashboard(self, house_id: int | None = None, current_user: User | None = None) -> OperationsDashboardResponse:
        if current_user is not None:
            self._ensure_view_permissions(current_user)

        ticket_q = self.db.query(Ticket)
        if house_id is not None:
            ticket_q = ticket_q.filter(Ticket.house_id == house_id)

        total_tickets = ticket_q.count()
        unassigned_tickets = ticket_q.filter(Ticket.status == TicketStatus.CREATED, Ticket.executor_id.is_(None)).count()
        assigned_tickets = ticket_q.filter(Ticket.status == TicketStatus.ASSIGNED).count()
        in_progress_tickets = ticket_q.filter(Ticket.status == TicketStatus.IN_PROGRESS).count()
        done_waiting_close_tickets = ticket_q.filter(Ticket.status == TicketStatus.DONE).count()

        complaint_q = self.db.query(TicketComplaint).filter(
            TicketComplaint.complaint_type == ComplaintType.QUALITY,
            TicketComplaint.status == ComplaintStatus.OPEN,
        )
        if house_id is not None:
            complaint_q = complaint_q.join(Ticket, Ticket.id == TicketComplaint.ticket_id).filter(Ticket.house_id == house_id)
        open_quality_complaints = complaint_q.count()

        remark_q = self.db.query(Remark).filter(Remark.status == RemarkStatus.ACTIVE)
        active_remarks = remark_q.count()

        return OperationsDashboardResponse(
            total_tickets=total_tickets,
            unassigned_tickets=unassigned_tickets,
            assigned_tickets=assigned_tickets,
            in_progress_tickets=in_progress_tickets,
            done_waiting_close_tickets=done_waiting_close_tickets,
            open_quality_complaints=open_quality_complaints,
            active_remarks=active_remarks,
        )

    def get_executor_load(self, house_id: int | None = None, current_user: User | None = None) -> list[ExecutorLoadResponse]:
        if current_user is not None:
            self._ensure_view_permissions(current_user)

        executors = self.db.query(User).filter(User.role == UserRole.EXECUTOR).order_by(User.full_name.asc()).all()
        results: list[ExecutorLoadResponse] = []

        for executor in executors:
            ticket_q = self.db.query(Ticket).filter(Ticket.executor_id == executor.id)
            if house_id is not None:
                ticket_q = ticket_q.filter(Ticket.house_id == house_id)

            assigned_tickets = ticket_q.filter(Ticket.status == TicketStatus.ASSIGNED).count()
            in_progress_tickets = ticket_q.filter(Ticket.status == TicketStatus.IN_PROGRESS).count()
            done_tickets = ticket_q.filter(Ticket.status == TicketStatus.DONE).count()

            active_remarks = self.db.query(func.count(Remark.id)).filter(
                Remark.executor_id == executor.id,
                Remark.status == RemarkStatus.ACTIVE,
            ).scalar() or 0

            complaint_q = self.db.query(func.count(TicketComplaint.id)).join(
                Ticket,
                Ticket.id == TicketComplaint.ticket_id,
            ).filter(
                Ticket.executor_id == executor.id,
                TicketComplaint.complaint_type == ComplaintType.QUALITY,
            )
            if house_id is not None:
                complaint_q = complaint_q.filter(Ticket.house_id == house_id)
            quality_complaints_on_tickets = complaint_q.scalar() or 0

            results.append(
                ExecutorLoadResponse(
                    executor_id=executor.id,
                    full_name=executor.full_name,
                    specialty=executor.specialty,
                    assigned_tickets=assigned_tickets,
                    in_progress_tickets=in_progress_tickets,
                    done_tickets=done_tickets,
                    active_remarks=active_remarks,
                    quality_complaints_on_tickets=quality_complaints_on_tickets,
                )
            )

        return results

    def get_executor_recommendations(
        self,
        current_user: User,
        house_id: int | None = None,
        category_id: int | None = None,
        top: int = 10,
    ) -> list[ExecutorRecommendationResponse]:
        self._ensure_view_permissions(current_user)

        category_name = None
        if category_id is not None:
            category = self.db.query(Category).filter(Category.id == category_id).first()
            if category:
                category_name = category.name.strip().lower()

        loads = self.get_executor_load(house_id=house_id)
        results: list[ExecutorRecommendationResponse] = []

        for item in loads:
            specialty = (item.specialty or "").strip().lower()
            matches_category = bool(category_name and specialty and category_name in specialty)

            active_score = round(
                item.in_progress_tickets * 2.0
                + item.assigned_tickets * 1.0
                + item.active_remarks * 1.5
                + item.quality_complaints_on_tickets * 2.5,
                2,
            )

            reasons: list[str] = []
            if matches_category:
                reasons.append("подходит по специализации")
            if item.in_progress_tickets == 0 and item.assigned_tickets == 0:
                reasons.append("сейчас почти нет активных заявок")
            elif active_score <= 3:
                reasons.append("относительно низкая текущая нагрузка")
            if item.active_remarks == 0:
                reasons.append("нет активных замечаний")
            if item.quality_complaints_on_tickets == 0:
                reasons.append("нет открытых жалоб по качеству")

            if not reasons:
                reasons.append("может быть назначен по общей загрузке")

            results.append(
                ExecutorRecommendationResponse(
                    executor_id=item.executor_id,
                    full_name=item.full_name,
                    specialty=item.specialty,
                    assigned_tickets=item.assigned_tickets,
                    in_progress_tickets=item.in_progress_tickets,
                    active_remarks=item.active_remarks,
                    open_quality_complaints=item.quality_complaints_on_tickets,
                    active_score=active_score,
                    matches_category=matches_category,
                    recommendation_reason=", ".join(reasons),
                )
            )

        results.sort(
            key=lambda x: (
                0 if x.matches_category else 1,
                x.active_score,
                x.open_quality_complaints,
                x.active_remarks,
                x.full_name.lower(),
            )
        )
        return results[:top]

    def bulk_assign_tickets(
        self,
        request: BulkAssignTicketsRequest,
        current_user: User,
    ) -> BulkTicketOperationResponse:
        self._ensure_manage_permissions(current_user)

        executor = self.db.query(User).filter(User.id == request.executor_id).first()
        if not executor or executor.role != UserRole.EXECUTOR:
            raise HTTPException(status_code=404, detail="Executor not found")

        ticket_ids = self._deduplicate_ids(request.ticket_ids)
        tickets = self.db.query(Ticket).filter(Ticket.id.in_(ticket_ids)).all()
        ticket_map = {ticket.id: ticket for ticket in tickets}

        now = datetime.utcnow()
        updated_ids: list[int] = []
        missing_ids: list[int] = []
        skipped: list[BulkTicketSkipResponse] = []
        resident_ids: set[int] = set()

        has_assigned_at = self._has_ticket_attr("assigned_at")
        has_planned_visit_at = self._has_ticket_attr("planned_visit_at")

        for ticket_id in ticket_ids:
            ticket = ticket_map.get(ticket_id)
            if ticket is None:
                missing_ids.append(ticket_id)
                continue

            if ticket.status in FINAL_STATUSES:
                skipped.append(self._build_skip(ticket_id, "Ticket already finished or canceled"))
                continue

            changed = False

            if ticket.executor_id != executor.id:
                ticket.executor_id = executor.id
                if has_assigned_at:
                    ticket.assigned_at = now
                changed = True

            if ticket.status == TicketStatus.CREATED:
                ticket.status = TicketStatus.ASSIGNED
                changed = True

            if request.planned_visit_at is not None and has_planned_visit_at:
                current_planned = getattr(ticket, "planned_visit_at", None)
                if current_planned != request.planned_visit_at:
                    ticket.planned_visit_at = request.planned_visit_at
                    changed = True

            if not changed:
                skipped.append(self._build_skip(ticket_id, "No changes required"))
                continue

            ticket.updated_at = now
            updated_ids.append(ticket.id)
            resident_ids.add(ticket.author_id)

        self.db.commit()

        if updated_ids:
            notification_service = NotificationService(self.db)
            notification_service.notify_user(
                user_id=executor.id,
                title="Вам назначены заявки",
                message=f"Назначено заявок: {len(updated_ids)}.",
                notif_type="bulk_ticket_assignment",
            )
            notification_service.notify_many(
                user_ids=resident_ids,
                title="Заявка передана исполнителю",
                message="По вашей заявке назначен исполнитель или обновлён план выезда.",
                notif_type="ticket_assignment_updated",
            )

        message = "Bulk assignment completed"
        if request.planned_visit_at is not None and not has_planned_visit_at:
            message += " (planned_visit_at field is not supported by current Ticket model)"

        return BulkTicketOperationResponse(
            requested_count=len(ticket_ids),
            updated_count=len(updated_ids),
            updated_ticket_ids=updated_ids,
            missing_ticket_ids=missing_ids,
            skipped=skipped,
            message=message,
        )

    def bulk_update_priority(
        self,
        request: BulkPriorityUpdateRequest,
        current_user: User,
    ) -> BulkTicketOperationResponse:
        self._ensure_manage_permissions(current_user)

        ticket_ids = self._deduplicate_ids(request.ticket_ids)

        if not self._has_ticket_attr("priority"):
            skipped = [
                self._build_skip(ticket_id, "Priority field is not supported by current Ticket model")
                for ticket_id in ticket_ids
            ]
            return BulkTicketOperationResponse(
                requested_count=len(ticket_ids),
                updated_count=0,
                updated_ticket_ids=[],
                missing_ticket_ids=[],
                skipped=skipped,
                message="Bulk priority update skipped: current Ticket model has no priority field",
            )

        tickets = self.db.query(Ticket).filter(Ticket.id.in_(ticket_ids)).all()
        ticket_map = {ticket.id: ticket for ticket in tickets}

        now = datetime.utcnow()
        updated_ids: list[int] = []
        missing_ids: list[int] = []
        skipped: list[BulkTicketSkipResponse] = []
        executor_ids: set[int] = set()

        has_first_response_due_at = self._has_ticket_attr("first_response_due_at")
        has_due_at = self._has_ticket_attr("due_at")

        for ticket_id in ticket_ids:
            ticket = ticket_map.get(ticket_id)
            if ticket is None:
                missing_ids.append(ticket_id)
                continue

            if ticket.status in FINAL_STATUSES:
                skipped.append(self._build_skip(ticket_id, "Cannot change priority for final ticket status"))
                continue

            changed = False
            if ticket.priority != request.priority:
                ticket.priority = request.priority
                changed = True

            if request.recalculate_due_dates and (has_first_response_due_at or has_due_at):
                first_response_due_at, due_at = self._priority_deadlines(ticket.created_at, request.priority)
                if has_first_response_due_at:
                    ticket.first_response_due_at = first_response_due_at
                if has_due_at:
                    ticket.due_at = due_at
                changed = True

            if not changed:
                skipped.append(self._build_skip(ticket_id, "No changes required"))
                continue

            ticket.updated_at = now
            if ticket.executor_id is not None:
                executor_ids.add(ticket.executor_id)
            updated_ids.append(ticket.id)

        self.db.commit()

        if updated_ids and executor_ids:
            notification_service = NotificationService(self.db)
            notification_service.notify_many(
                user_ids=executor_ids,
                title="Приоритет заявок изменён",
                message=f"Для части назначенных вам заявок был обновлён приоритет: {request.priority.value}.",
                notif_type="ticket_priority_updated",
            )

        message = "Bulk priority update completed"
        if request.recalculate_due_dates and not (has_first_response_due_at or has_due_at):
            message += " (deadline fields are not supported by current Ticket model)"

        return BulkTicketOperationResponse(
            requested_count=len(ticket_ids),
            updated_count=len(updated_ids),
            updated_ticket_ids=updated_ids,
            missing_ticket_ids=missing_ids,
            skipped=skipped,
            message=message,
        )

    def bulk_plan_visit(
        self,
        request: BulkPlanVisitRequest,
        current_user: User,
    ) -> BulkTicketOperationResponse:
        self._ensure_manage_permissions(current_user)

        ticket_ids = self._deduplicate_ids(request.ticket_ids)

        if not self._has_ticket_attr("planned_visit_at"):
            skipped = [
                self._build_skip(ticket_id, "planned_visit_at field is not supported by current Ticket model")
                for ticket_id in ticket_ids
            ]
            return BulkTicketOperationResponse(
                requested_count=len(ticket_ids),
                updated_count=0,
                updated_ticket_ids=[],
                missing_ticket_ids=[],
                skipped=skipped,
                message="Bulk planned visit update skipped: current Ticket model has no planned_visit_at field",
            )

        tickets = self.db.query(Ticket).filter(Ticket.id.in_(ticket_ids)).all()
        ticket_map = {ticket.id: ticket for ticket in tickets}

        now = datetime.utcnow()
        updated_ids: list[int] = []
        missing_ids: list[int] = []
        skipped: list[BulkTicketSkipResponse] = []
        notify_user_ids: set[int] = set()

        for ticket_id in ticket_ids:
            ticket = ticket_map.get(ticket_id)
            if ticket is None:
                missing_ids.append(ticket_id)
                continue

            if ticket.status in FINAL_STATUSES:
                skipped.append(self._build_skip(ticket_id, "Cannot plan visit for final ticket status"))
                continue

            if ticket.planned_visit_at == request.planned_visit_at:
                skipped.append(self._build_skip(ticket_id, "Planned visit already set to this value"))
                continue

            ticket.planned_visit_at = request.planned_visit_at
            ticket.updated_at = now
            updated_ids.append(ticket.id)
            notify_user_ids.add(ticket.author_id)
            if ticket.executor_id is not None:
                notify_user_ids.add(ticket.executor_id)

        self.db.commit()

        if updated_ids and notify_user_ids:
            notification_service = NotificationService(self.db)
            notification_service.notify_many(
                user_ids=notify_user_ids,
                title="Запланирован визит по заявке",
                message=f"Новая плановая дата визита: {request.planned_visit_at.strftime('%Y-%m-%d %H:%M')}.",
                notif_type="planned_visit_updated",
            )

        return BulkTicketOperationResponse(
            requested_count=len(ticket_ids),
            updated_count=len(updated_ids),
            updated_ticket_ids=updated_ids,
            missing_ticket_ids=missing_ids,
            skipped=skipped,
            message="Bulk planned visit update completed",
        )
