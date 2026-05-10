import os
import shutil
import uuid
from datetime import datetime, timedelta

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.profanity import ensure_clean_text
from app.models.history import TicketHistory
from app.models.ticket import Ticket, TicketStatus
from app.models.ticket_complaint import (
    ComplaintComment,
    ComplaintFile,
    ComplaintStatus,
    ComplaintType,
    TicketComplaint,
)
from app.models.user import User, UserRole
from app.services.app_settings_service import AppSettingsService
from app.services.live_update_hub import live_update_hub
from app.services.notification_service import NotificationService
from app.services.ticket_service import TicketService


class TicketComplaintService:
    STAFF_ONLY_PREFIX = "[[staff]] "
    RESIDENT_ONLY_PREFIX = "[[resident]] "

    def __init__(self, db: Session):
        self.db = db
        self.notif = NotificationService(db)
        self.settings_service = AppSettingsService(db)
        self.ticket_service = TicketService(db)

    def _get_ticket_or_404(self, ticket_id: int) -> Ticket:
        ticket = self.db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")
        return ticket

    def _get_complaint_or_404(self, complaint_id: int) -> TicketComplaint:
        complaint = self.db.query(TicketComplaint).filter(TicketComplaint.id == complaint_id).first()
        if not complaint:
            raise HTTPException(status_code=404, detail="Complaint not found")
        return complaint

    def _get_accessible_complaint(self, complaint_id: int, user: User) -> TicketComplaint:
        complaint = self._get_complaint_or_404(complaint_id)
        self._ensure_can_view_complaint(complaint, user)
        return complaint

    def _ensure_staff(self, user: User):
        if user.role not in [UserRole.ADMIN, UserRole.DISPATCHER, UserRole.AUDITOR]:
            raise HTTPException(status_code=403, detail="Not enough permissions")

    def _ensure_can_view_complaint(self, complaint: TicketComplaint, user: User):
        if user.role == UserRole.ADMIN:
            return
        if user.role == UserRole.AUDITOR:
            return
        if user.role == UserRole.DISPATCHER and complaint.complaint_type != ComplaintType.DISPATCHER_INACTION:
            return
        if user.role == UserRole.RESIDENT and complaint.author_id == user.id:
            return
        raise HTTPException(status_code=403, detail="Not enough permissions")

    def _get_escalation_threshold_minutes(self) -> int:
        settings = self.settings_service.get_settings()
        return int(settings.complaint_escalate_after_minutes or 360)

    def _get_overdue_threshold_minutes(self) -> int:
        settings = self.settings_service.get_settings()
        return int(settings.complaint_overdue_after_minutes or 360)

    def _get_primary_complaint_limit(self) -> int:
        settings = self.settings_service.get_settings()
        return int(getattr(settings, "complaint_primary_limit", None) or 2)

    def _has_auditor(self) -> bool:
        return self.db.query(User.id).filter(User.role == UserRole.AUDITOR).first() is not None

    def _format_duration_minutes_ru(self, total_minutes: int) -> str:
        minutes = max(0, int(total_minutes or 0))
        hours = minutes // 60
        rest_minutes = minutes % 60
        parts: list[str] = []

        if hours:
            parts.append(f"{hours} {self._pluralize_ru(hours, 'час', 'часа', 'часов')}")
        if rest_minutes:
            parts.append(f"{rest_minutes} {self._pluralize_ru(rest_minutes, 'минуту', 'минуты', 'минут')}")

        return " ".join(parts) or "0 минут"

    def _complaint_type_label(self, complaint_type: ComplaintType) -> str:
        labels = {
            ComplaintType.QUALITY: "жалоба на качество",
            ComplaintType.OVERDUE: "жалоба на отсутствие реакции",
            ComplaintType.DISPATCHER_INACTION: "обращение в контролирующий орган",
        }
        return labels.get(complaint_type, str(complaint_type.value if hasattr(complaint_type, "value") else complaint_type))

    def _complaint_decision_label(self, complaint: TicketComplaint) -> str:
        if complaint.status == ComplaintStatus.RESOLVED:
            return "принята"
        if complaint.status == ComplaintStatus.DISMISSED:
            comment = (complaint.resolution_comment or "").lower()
            if "отозвана жителем" in comment:
                return "отменена"
            return "отклонена"
        return "обновлена"

    def _ticket_status_value(self, ticket: Ticket) -> str:
        return ticket.status.value if hasattr(ticket.status, "value") else str(ticket.status)

    def _add_ticket_history_for_complaint(
        self,
        ticket: Ticket,
        user: User | None,
        comment: str,
        *,
        old_status: str | None = None,
        new_status: str | None = None,
    ) -> None:
        status_value = self._ticket_status_value(ticket)
        self.db.add(
            TicketHistory(
                ticket_id=ticket.id,
                user_id=user.id if user else None,
                old_status=old_status if old_status is not None else status_value,
                new_status=new_status if new_status is not None else status_value,
                comment=comment,
                created_at=datetime.utcnow(),
            )
        )

    def _pluralize_ru(self, value: int, one: str, few: str, many: str) -> str:
        abs_value = abs(int(value)) % 100
        last = abs_value % 10
        if 10 < abs_value < 20:
            return many
        if 1 < last < 5:
            return few
        if last == 1:
            return one
        return many

    def _comment_visibility(self, raw_message: str | None) -> str:
        text = str(raw_message or "")
        if text.startswith(self.STAFF_ONLY_PREFIX):
            return "staff"
        if text.startswith(self.RESIDENT_ONLY_PREFIX):
            return "resident"
        return "public"

    def _clean_comment_message(self, raw_message: str | None) -> str:
        text = str(raw_message or "")
        if text.startswith(self.STAFF_ONLY_PREFIX):
            return text[len(self.STAFF_ONLY_PREFIX):].strip()
        if text.startswith(self.RESIDENT_ONLY_PREFIX):
            return text[len(self.RESIDENT_ONLY_PREFIX):].strip()
        return text.strip()

    def _encode_comment_message(self, message: str, visibility: str) -> str:
        clean = message.strip()
        if visibility == "staff":
            return f"{self.STAFF_ONLY_PREFIX}{clean}"
        if visibility == "resident":
            return f"{self.RESIDENT_ONLY_PREFIX}{clean}"
        return clean

    def _comment_visible_for_user(self, complaint: TicketComplaint, comment: ComplaintComment, user: User) -> bool:
        visibility = self._comment_visibility(comment.message)
        if visibility == "staff":
            return user.role != UserRole.RESIDENT
        if visibility == "resident":
            if user.role in [UserRole.ADMIN, UserRole.AUDITOR]:
                return True
            return user.role == UserRole.RESIDENT and complaint.author_id == user.id
        return True

    def _serialize_comment(self, comment: ComplaintComment) -> dict:
        return {
            "id": comment.id,
            "complaint_id": comment.complaint_id,
            "author_id": comment.author_id,
            "author_name": comment.author_name,
            "author_role": comment.author_role,
            "message": self._clean_comment_message(comment.message),
            "visibility": self._comment_visibility(comment.message),
            "created_at": comment.created_at,
        }

    def _serialize_complaint(self, complaint: TicketComplaint, user: User, include_comments: bool = True) -> dict:
        return {
            "id": complaint.id,
            "ticket_id": complaint.ticket_id,
            "author_id": complaint.author_id,
            "author_name": complaint.author_name,
            "complaint_type": complaint.complaint_type,
            "description": complaint.description,
            "parent_complaint_id": complaint.parent_complaint_id,
            "status": complaint.status,
            "created_at": complaint.created_at,
            "resolver_id": complaint.resolver_id,
            "resolver_name": complaint.resolver_name,
            "resolver_role": complaint.resolver_role,
            "resolved_at": complaint.resolved_at,
            "resolution_comment": complaint.resolution_comment,
            "files": [
                {
                    "id": file.id,
                    "file_path": file.file_path,
                    "created_at": file.created_at,
                }
                for file in (complaint.files or [])
            ],
            "comments": [
                self._serialize_comment(comment)
                for comment in (complaint.comments or [])
                if self._comment_visible_for_user(complaint, comment, user)
            ] if include_comments else [],
        }

    def _broadcast_complaint_update(self, complaint: TicketComplaint, action: str = "updated", **extra) -> None:
        if complaint is None:
            return

        payload = {
            "entity": "complaint",
            "action": action,
            "complaint_id": complaint.id,
            "ticket_id": complaint.ticket_id,
            "complaint_type": complaint.complaint_type.value if hasattr(complaint.complaint_type, "value") else str(complaint.complaint_type),
            "status": complaint.status.value if hasattr(complaint.status, "value") else str(complaint.status),
        }
        payload.update(extra)
        live_update_hub.broadcast_from_sync(payload)

    def _notify_complaint_created(self, complaint: TicketComplaint, ticket: Ticket) -> None:
        if complaint.complaint_type == ComplaintType.DISPATCHER_INACTION:
            roles = [UserRole.ADMIN, UserRole.AUDITOR]
            title = "Новое обращение в контролирующий орган"
            message = f"Житель направил обращение по заявке #{ticket.id}"
        else:
            roles = [UserRole.ADMIN, UserRole.DISPATCHER, UserRole.AUDITOR]
            title = "Новая жалоба"
            message = f"Жалоба по заявке #{ticket.id}: {self._complaint_type_label(complaint.complaint_type)}"

        self.notif.notify_roles(
            roles=roles,
            title=title,
            message=message,
            notif_type="complaint_created",
            ticket_id=ticket.id,
            complaint_id=complaint.id,
        )

    def _notify_comment_created(self, complaint: TicketComplaint, comment: ComplaintComment, author: User) -> None:
        recipient_ids: set[int] = set()
        visibility = self._comment_visibility(comment.message)

        if visibility in ["public", "resident"] and complaint.author_id != author.id:
            recipient_ids.add(complaint.author_id)

        if visibility == "resident":
            staff_roles = [UserRole.ADMIN, UserRole.AUDITOR]
        else:
            staff_roles = (
                [UserRole.ADMIN, UserRole.AUDITOR]
                if complaint.complaint_type == ComplaintType.DISPATCHER_INACTION
                else [UserRole.ADMIN, UserRole.DISPATCHER, UserRole.AUDITOR]
            )
        staff_users = self.db.query(User).filter(User.role.in_(staff_roles)).all()
        for staff_user in staff_users:
            if staff_user.id != author.id:
                recipient_ids.add(staff_user.id)

        if not recipient_ids:
            return

        self.notif.notify_many(
            user_ids=recipient_ids,
            title=f"Новый комментарий по жалобе #{complaint.id}",
            message=self._clean_comment_message(comment.message),
            notif_type="complaint_comment",
            ticket_id=complaint.ticket_id,
            complaint_id=complaint.id,
        )

    def create_complaint(self, data, user: User):
        if user.role != UserRole.RESIDENT:
            raise HTTPException(status_code=403, detail="Only residents can create complaints")

        ensure_clean_text(data.description)

        ticket = self._get_ticket_or_404(data.ticket_id)

        if ticket.author_id != user.id:
            raise HTTPException(status_code=403, detail="You can complain only about your ticket")

        now = datetime.utcnow()
        parent_complaint = None

        if data.complaint_type == ComplaintType.OVERDUE:
            if ticket.status in [TicketStatus.DONE, TicketStatus.CLOSED, TicketStatus.CANCELED]:
                raise HTTPException(status_code=400, detail="Жалобу на отсутствие реакции можно подать только по незавершённой заявке")

            overdue_threshold_minutes = self._get_overdue_threshold_minutes()
            threshold = now - timedelta(minutes=overdue_threshold_minutes)
            if not ticket.created_at or ticket.created_at > threshold:
                raise HTTPException(
                    status_code=400,
                    detail=f"Жалобу на отсутствие реакции можно подать после {self._format_duration_minutes_ru(overdue_threshold_minutes)} ожидания",
                )

        elif data.complaint_type == ComplaintType.QUALITY:
            if ticket.status != TicketStatus.DONE:
                raise HTTPException(
                    status_code=400,
                    detail="Жалобу на качество можно подать только после выполнения заявки и до её принятия жителем",
                )

        if data.complaint_type in [ComplaintType.QUALITY, ComplaintType.OVERDUE]:
            primary_limit = self._get_primary_complaint_limit()
            primary_count = self.db.query(TicketComplaint).filter(
                TicketComplaint.ticket_id == ticket.id,
                TicketComplaint.author_id == user.id,
                TicketComplaint.complaint_type.in_([ComplaintType.QUALITY, ComplaintType.OVERDUE]),
            ).count()
            if primary_count >= primary_limit:
                raise HTTPException(
                    status_code=400,
                    detail=f"По этой заявке можно отправить не более {primary_limit} обычных жалоб",
                )

            existing_primary = self.db.query(TicketComplaint).filter(
                TicketComplaint.ticket_id == ticket.id,
                TicketComplaint.author_id == user.id,
                TicketComplaint.status == ComplaintStatus.OPEN,
            ).first()
            if existing_primary:
                raise HTTPException(status_code=400, detail="По этой заявке уже есть открытая жалоба")

        elif data.complaint_type == ComplaintType.DISPATCHER_INACTION:
            if not self._has_auditor():
                raise HTTPException(
                    status_code=503,
                    detail="Отправка жалобы в контролирующий орган на данный момент недоступна",
                )
            if not data.parent_complaint_id:
                raise HTTPException(status_code=400, detail="parent_complaint_id is required")

            parent_complaint = self._get_complaint_or_404(data.parent_complaint_id)
            if parent_complaint.ticket_id != ticket.id:
                raise HTTPException(status_code=400, detail="Parent complaint must belong to the same ticket")
            if parent_complaint.author_id != user.id:
                raise HTTPException(status_code=403, detail="Parent complaint must belong to current resident")
            if parent_complaint.complaint_type not in [ComplaintType.QUALITY, ComplaintType.OVERDUE]:
                raise HTTPException(status_code=400, detail="Обращение в контролирующий орган доступно только для жалобы на качество или отсутствие реакции")
            if parent_complaint.status not in [ComplaintStatus.OPEN, ComplaintStatus.DISMISSED, ComplaintStatus.RESOLVED]:
                raise HTTPException(
                    status_code=400,
                    detail="Обращение в контролирующий орган доступно только по открытой, принятой или отклонённой жалобе",
                )

            if parent_complaint.status == ComplaintStatus.OPEN:
                threshold_minutes = self._get_escalation_threshold_minutes()
                available_after = parent_complaint.created_at + timedelta(minutes=threshold_minutes)
                if datetime.utcnow() < available_after:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Обращение в контролирующий орган станет доступно через {self._format_duration_minutes_ru(threshold_minutes)}",
                    )

        existing_query = self.db.query(TicketComplaint).filter(
            TicketComplaint.ticket_id == ticket.id,
            TicketComplaint.complaint_type == data.complaint_type,
            TicketComplaint.status == ComplaintStatus.OPEN,
        )
        if data.complaint_type == ComplaintType.DISPATCHER_INACTION and data.parent_complaint_id:
            existing_query = existing_query.filter(TicketComplaint.parent_complaint_id == data.parent_complaint_id)
        existing = existing_query.first()
        if existing:
            raise HTTPException(status_code=400, detail="Жалоба уже существует")

        complaint = TicketComplaint(
            ticket_id=ticket.id,
            author_id=user.id,
            complaint_type=data.complaint_type,
            description=data.description,
            status=ComplaintStatus.OPEN,
            created_at=now,
            parent_complaint_id=parent_complaint.id if parent_complaint else None,
        )
        self.db.add(complaint)
        self.db.flush()
        if data.complaint_type == ComplaintType.DISPATCHER_INACTION:
            history_comment = (
                f"Житель направил обращение в контролирующий орган. Обращение #{complaint.id}."
                + (f" Основание: жалоба #{parent_complaint.id}." if parent_complaint else "")
            )
        else:
            history_comment = f"Житель подал жалобу: {self._complaint_type_label(data.complaint_type)}. Жалоба #{complaint.id}."
        self._add_ticket_history_for_complaint(ticket, user, history_comment)
        self.db.commit()
        self.db.refresh(complaint)

        self._notify_complaint_created(complaint, ticket)
        self.ticket_service._broadcast_ticket_update(ticket, action="complaint_created", complaint_id=complaint.id)
        self._broadcast_complaint_update(complaint, action="created")
        return self._serialize_complaint(complaint, user)

    def list_complaints(
        self,
        user: User,
        status: ComplaintStatus | None = None,
        complaint_type: ComplaintType | None = None,
        ticket_id: int | None = None,
        skip: int = 0,
        limit: int = 100,
    ):
        if user.role == UserRole.EXECUTOR:
            raise HTTPException(status_code=403, detail="Executors cannot view complaints")

        query = self.db.query(TicketComplaint)

        if user.role == UserRole.RESIDENT:
            query = query.filter(TicketComplaint.author_id == user.id)
        elif user.role == UserRole.DISPATCHER:
            query = query.filter(TicketComplaint.complaint_type != ComplaintType.DISPATCHER_INACTION)

        if status:
            query = query.filter(TicketComplaint.status == status)
        if complaint_type:
            query = query.filter(TicketComplaint.complaint_type == complaint_type)
        if ticket_id:
            query = query.filter(TicketComplaint.ticket_id == ticket_id)

        return [
            self._serialize_complaint(item, user, include_comments=False)
            for item in query.order_by(TicketComplaint.created_at.desc()).offset(skip).limit(limit).all()
        ]

    def get_by_id(self, complaint_id: int, user: User):
        complaint = self._get_accessible_complaint(complaint_id, user)
        return self._serialize_complaint(complaint, user)

    def list_comments(self, complaint_id: int, user: User):
        complaint = self._get_accessible_complaint(complaint_id, user)
        return [
            self._serialize_comment(comment)
            for comment in complaint.comments
            if self._comment_visible_for_user(complaint, comment, user)
        ]

    def create_comment(self, complaint_id: int, message: str, user: User, visibility: str | None = None):
        complaint = self._get_accessible_complaint(complaint_id, user)

        if complaint.status != ComplaintStatus.OPEN:
            raise HTTPException(status_code=400, detail="Cannot comment closed complaint")

        if user.role == UserRole.RESIDENT:
            if complaint.author_id != user.id:
                raise HTTPException(status_code=403, detail="Only complaint author can comment")
            self.ticket_service._ensure_resident_not_banned(user)
        else:
            self._ensure_staff(user)

        if not message or not message.strip():
            raise HTTPException(status_code=400, detail="message is required")

        ensure_clean_text(message)

        normalized_visibility = "public"
        if visibility and str(visibility).strip().lower() == "staff":
            if user.role == UserRole.RESIDENT:
                raise HTTPException(status_code=403, detail="Residents cannot send private staff messages")
            normalized_visibility = "staff"

        comment = ComplaintComment(
            complaint_id=complaint.id,
            author_id=user.id,
            message=self._encode_comment_message(message, normalized_visibility),
            created_at=datetime.utcnow(),
        )
        self.db.add(comment)
        self.db.flush()

        mirrored_parent_comment = None
        if (
            complaint.complaint_type == ComplaintType.DISPATCHER_INACTION
            and normalized_visibility == "staff"
            and complaint.parent_complaint is not None
        ):
            mirrored_parent_comment = ComplaintComment(
                complaint_id=complaint.parent_complaint.id,
                author_id=user.id,
                message=self._encode_comment_message(
                    f"Сообщение по обращению в контролирующий орган: {message.strip()}",
                    "staff",
                ),
                created_at=datetime.utcnow(),
            )
            self.db.add(mirrored_parent_comment)
            self.db.flush()

        self.db.commit()
        self.db.refresh(comment)
        if mirrored_parent_comment is not None:
            self._notify_comment_created(complaint.parent_complaint, mirrored_parent_comment, user)
            self._broadcast_complaint_update(
                complaint.parent_complaint,
                action="comment_created",
                comment_id=mirrored_parent_comment.id,
                author_id=user.id,
            )
        self._notify_comment_created(complaint, comment, user)
        self._broadcast_complaint_update(complaint, action="comment_created", comment_id=comment.id, author_id=user.id)
        return self._serialize_comment(comment)

    def add_photo(self, complaint_id: int, file: UploadFile, user: User) -> ComplaintFile:
        complaint = self._get_accessible_complaint(complaint_id, user)

        if complaint.status != ComplaintStatus.OPEN:
            raise HTTPException(status_code=400, detail="Cannot add photo to closed complaint")

        if not (user.role in [UserRole.ADMIN, UserRole.DISPATCHER, UserRole.AUDITOR] or complaint.author_id == user.id):
            raise HTTPException(status_code=403, detail="Not enough permissions")

        if user.role == UserRole.RESIDENT:
            self.ticket_service._ensure_resident_not_banned(user)

        file_ext = file.filename.split(".")[-1] if file.filename and "." in file.filename else "jpg"
        unique_name = f"{uuid.uuid4()}.{file_ext}"

        dir_path = os.path.join("static", "uploads", "complaints", str(complaint.id))
        os.makedirs(dir_path, exist_ok=True)

        save_path = os.path.join(dir_path, unique_name)
        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        db_file = ComplaintFile(
            complaint_id=complaint.id,
            file_path="/" + save_path.replace("\\", "/"),
            created_at=datetime.utcnow(),
        )
        self.db.add(db_file)
        self.db.commit()
        self.db.refresh(db_file)
        self._broadcast_complaint_update(complaint, action="file_uploaded", file_id=db_file.id)
        return db_file

    def resolve(self, complaint_id: int, data, user: User):
        self._ensure_staff(user)

        complaint = self._get_complaint_or_404(complaint_id)

        if complaint.status != ComplaintStatus.OPEN:
            raise HTTPException(status_code=400, detail="Complaint already closed")

        if data.status not in [ComplaintStatus.RESOLVED, ComplaintStatus.DISMISSED]:
            raise HTTPException(status_code=400, detail="Invalid status")

        resident_resolution_comment = (
            data.resident_resolution_comment
            if data.resident_resolution_comment is not None
            else data.resolution_comment
        )
        resident_resolution_comment = resident_resolution_comment.strip() if resident_resolution_comment else None
        staff_comment = data.staff_comment.strip() if data.staff_comment else None
        ensure_clean_text(resident_resolution_comment, staff_comment)

        if data.status == ComplaintStatus.DISMISSED and not resident_resolution_comment:
            raise HTTPException(status_code=400, detail="Reason is required when dismissing complaint")

        if complaint.complaint_type == ComplaintType.DISPATCHER_INACTION and user.role not in [UserRole.ADMIN, UserRole.AUDITOR]:
            raise HTTPException(status_code=403, detail="Only admin or auditor can resolve escalated complaints")

        complaint.status = data.status
        complaint.resolver_id = user.id
        complaint.resolved_at = datetime.utcnow()
        complaint.resolution_comment = resident_resolution_comment

        ticket = self._get_ticket_or_404(complaint.ticket_id)
        ticket_was_updated = False
        if complaint.complaint_type in [ComplaintType.QUALITY, ComplaintType.OVERDUE] and data.status == ComplaintStatus.RESOLVED:
            old_status_value = self._ticket_status_value(ticket)
            should_reset_assignment = (
                complaint.complaint_type == ComplaintType.QUALITY
                or ticket.status in [TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS]
                or ticket.executor_id is not None
            )

            if should_reset_assignment:
                ticket.status = TicketStatus.CREATED
                ticket.executor_id = None
                ticket.assigned_at = None
                ticket.started_at = None
                ticket.done_at = None

            if complaint.complaint_type == ComplaintType.QUALITY:
                history_comment = "Жалоба на качество принята. Заявка возвращена на повторную обработку и ожидает нового назначения исполнителя."
            elif should_reset_assignment:
                history_comment = "Жалоба на отсутствие реакции принята. Назначение исполнителя снято, заявка возвращена диспетчеру для повторной обработки."
            else:
                history_comment = "Жалоба на отсутствие реакции принята. Заявка требует реакции диспетчера."

            self._add_ticket_history_for_complaint(
                ticket,
                user,
                f"{history_comment} Жалоба #{complaint.id}."
                + (f" Комментарий: {resident_resolution_comment}" if resident_resolution_comment else ""),
                old_status=old_status_value,
                new_status=TicketStatus.CREATED.value if should_reset_assignment else old_status_value,
            )
            ticket_was_updated = True
        elif data.status == ComplaintStatus.DISMISSED:
            self._add_ticket_history_for_complaint(
                ticket,
                user,
                f"Жалоба отклонена: {self._complaint_type_label(complaint.complaint_type)}. Жалоба #{complaint.id}."
                + (f" Комментарий: {resident_resolution_comment}" if resident_resolution_comment else ""),
            )
            ticket_was_updated = True

        if complaint.complaint_type == ComplaintType.DISPATCHER_INACTION and data.status == ComplaintStatus.RESOLVED:
            self._add_ticket_history_for_complaint(
                ticket,
                user,
                f"Обращение в контролирующий орган принято. Обращение #{complaint.id}. Предыдущая жалоба возвращена на повторное рассмотрение."
                + (f" Комментарий жителю: {resident_resolution_comment}" if resident_resolution_comment else ""),
            )
            ticket_was_updated = True
            parent_complaint = complaint.parent_complaint
            if parent_complaint and parent_complaint.complaint_type in [ComplaintType.QUALITY, ComplaintType.OVERDUE]:
                parent_complaint.status = ComplaintStatus.OPEN
                parent_complaint.resolver_id = None
                parent_complaint.resolved_at = None
                parent_complaint.resolution_comment = None

                parent_comment = ComplaintComment(
                    complaint_id=parent_complaint.id,
                    author_id=user.id,
                    message="Контролирующий орган принял обращение. Жалоба возвращена на повторное рассмотрение.",
                    created_at=datetime.utcnow(),
                )
                self.db.add(parent_comment)
                self.db.flush()
                self._notify_comment_created(parent_complaint, parent_comment, user)

                if resident_resolution_comment:
                    resident_parent_comment = ComplaintComment(
                        complaint_id=parent_complaint.id,
                        author_id=user.id,
                        message=self._encode_comment_message(
                            f"Сообщение жителю: {resident_resolution_comment}",
                            "resident",
                        ),
                        created_at=datetime.utcnow(),
                    )
                    self.db.add(resident_parent_comment)
                    self.db.flush()
                    self._notify_comment_created(parent_complaint, resident_parent_comment, user)

                if staff_comment:
                    staff_parent_comment = ComplaintComment(
                        complaint_id=parent_complaint.id,
                        author_id=user.id,
                        message=self._encode_comment_message(
                            f"Предписание контролирующего органа: {staff_comment}",
                            "staff",
                        ),
                        created_at=datetime.utcnow(),
                    )
                    self.db.add(staff_parent_comment)
                    self.db.flush()
                    self._notify_comment_created(parent_complaint, staff_parent_comment, user)
        elif staff_comment:
            internal_comment = ComplaintComment(
                complaint_id=complaint.id,
                author_id=user.id,
                message=self._encode_comment_message(staff_comment, "staff"),
                created_at=datetime.utcnow(),
            )
            self.db.add(internal_comment)
            self.db.flush()
            self._notify_comment_created(complaint, internal_comment, user)

        self.db.commit()
        self.db.refresh(complaint)
        if ticket_was_updated:
            self.db.refresh(ticket)
        if complaint.parent_complaint_id and complaint.parent_complaint is not None:
            self.db.refresh(complaint.parent_complaint)

        decision_label = self._complaint_decision_label(complaint)
        self.notif.notify_user(
            user_id=complaint.author_id,
            title=f"Жалоба {decision_label}",
            message=(
                f"Жалоба #{complaint.id} по заявке #{complaint.ticket_id} {decision_label}"
                + (f". Комментарий: {complaint.resolution_comment}" if complaint.resolution_comment else "")
            ),
            notif_type="complaint_resolved",
            ticket_id=complaint.ticket_id,
            complaint_id=complaint.id,
        )

        if complaint.parent_complaint_id and complaint.parent_complaint is not None:
            self._broadcast_complaint_update(complaint.parent_complaint, action="reopened")
        if ticket_was_updated:
            self.ticket_service._broadcast_ticket_update(ticket, action="complaint_resolved")
        self._broadcast_complaint_update(complaint, action="resolved")

        return self._serialize_complaint(complaint, user)

    def cancel_complaint(self, complaint_id: int, user: User):
        complaint = self._get_complaint_or_404(complaint_id)

        if user.role != UserRole.RESIDENT or complaint.author_id != user.id:
            raise HTTPException(status_code=403, detail="Only complaint author can cancel it")

        self.ticket_service._ensure_resident_not_banned(user)

        if complaint.status != ComplaintStatus.OPEN:
            raise HTTPException(status_code=400, detail="Only open complaint can be canceled")

        complaint.status = ComplaintStatus.DISMISSED
        complaint.resolver_id = user.id
        complaint.resolved_at = datetime.utcnow()
        complaint.resolution_comment = "Жалоба отозвана жителем"
        ticket = self._get_ticket_or_404(complaint.ticket_id)
        self._add_ticket_history_for_complaint(
            ticket,
            user,
            f"Житель отменил жалобу: {self._complaint_type_label(complaint.complaint_type)}. Жалоба #{complaint.id}.",
        )

        self.db.commit()
        self.db.refresh(complaint)
        self.ticket_service._broadcast_ticket_update(ticket, action="complaint_canceled", complaint_id=complaint.id)
        self._broadcast_complaint_update(complaint, action="canceled")
        return self._serialize_complaint(complaint, user)
