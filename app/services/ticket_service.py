import os
import shutil
import uuid
from datetime import datetime
from typing import List

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.profanity import ensure_clean_text
from app.models.category import Category
from app.models.executor import ExecutorProfile
from app.models.history import TicketHistory
from app.models.location import Apartment
from app.models.ticket import Ticket, TicketFile, TicketFileKind, TicketPriority, TicketStatus
from app.models.user import User, UserRole
from app.repositories.ticket_repository import TicketRepository
from app.repositories.user_repository import UserRepository
from app.schemas.ticket import TicketAssign, TicketCancelRequest, TicketCreate, TicketUpdate
from app.services.executor_availability import get_executor_availability_state, moscow_today
from app.services.live_update_hub import live_update_hub
from app.services.notification_service import NotificationService


class TicketService:
    EXECUTOR_COMMENT_PREFIX = "Комментарий мастера:"
    RESIDENT_REVIEW_PREFIX = "Отзыв жильца:"
    RESIDENT_CANCEL_REASONS = {
        "too_long": "Слишком долго ждать",
        "price": "Не устроила цена",
        "not_needed": "Больше нет необходимости в помощи специалиста",
    }

    def __init__(self, db: Session):
        self.db = db
        self.ticket_repo = TicketRepository(db)
        self.user_repo = UserRepository(db)

    def _get_ticket_or_404(self, ticket_id: int) -> Ticket:
        ticket = self.ticket_repo.get_by_id(ticket_id)
        if not ticket:
            raise HTTPException(status_code=404, detail="Заявка не найдена")
        return ticket

    def get_ticket_by_id(self, ticket_id: int, current_user: User) -> Ticket:
        return self.get_ticket(ticket_id, current_user)

    def _ensure_resident_not_banned(self, current_user: User) -> None:
        if current_user.role != UserRole.RESIDENT:
            return

        if current_user.banned_until and current_user.banned_until > datetime.utcnow():
            banned_until = current_user.banned_until.strftime("%Y-%m-%d %H:%M:%S")
            raise HTTPException(
                status_code=403,
                detail=f"Создание заявок временно недоступно до {banned_until}",
            )

    def _ensure_category_type(self, category_id: int | None, category_type: str, field_name: str) -> None:
        if category_id is None:
            return
        category = (
            self.db.query(Category)
            .filter(Category.id == category_id, Category.category_type == category_type)
            .first()
        )
        if not category:
            raise HTTPException(status_code=400, detail=f"Unsupported {field_name}")

    def _add_history(
        self,
        ticket_id: int,
        user_id: int | None = None,
        old_status: str | None = None,
        new_status: str | None = None,
        comment: str | None = None,
    ):
        history = TicketHistory(
            ticket_id=ticket_id,
            user_id=user_id,
            old_status=old_status,
            new_status=new_status,
            comment=comment,
            created_at=datetime.utcnow(),
        )
        self.db.add(history)
        self.db.flush()
        return history

    def _split_result_comment(self, result_comment: str | None) -> tuple[str, str]:
        text = (result_comment or "").strip()
        if not text:
            return "", ""

        review = ""
        if self.RESIDENT_REVIEW_PREFIX in text:
            before, after = text.split(self.RESIDENT_REVIEW_PREFIX, 1)
            text = before.strip()
            review = after.strip()

        executor_comment = text.replace(self.EXECUTOR_COMMENT_PREFIX, "", 1).strip()
        return executor_comment, review

    def _compose_result_comment(self, executor_comment: str = "", resident_review: str = "") -> str | None:
        parts = []
        if executor_comment:
            parts.append(f"{self.EXECUTOR_COMMENT_PREFIX} {executor_comment}")
        if resident_review:
            parts.append(f"{self.RESIDENT_REVIEW_PREFIX} {resident_review}")
        return "\n\n".join(parts) if parts else None

    def _format_actor_name(self, user: User | None) -> str:
        if user is None:
            return "пользователь"
        return (getattr(user, "full_name", None) or getattr(user, "login", None) or "пользователь").strip()

    def _broadcast_ticket_update(self, ticket: Ticket, action: str = "updated", **extra) -> None:
        if ticket is None:
            return

        payload = {
            "entity": "ticket",
            "action": action,
            "ticket_id": ticket.id,
            "executor_id": ticket.executor_id,
        }
        if ticket.house_id is not None:
            payload["house_id"] = ticket.house_id
        if ticket.author_id is not None:
            payload["author_id"] = ticket.author_id
        if ticket.status is not None:
            payload["status"] = ticket.status.value if hasattr(ticket.status, "value") else str(ticket.status)
        payload.update(extra)
        live_update_hub.broadcast_from_sync(payload)

    def _notify_user_ids(
        self,
        user_ids: set[int] | list[int],
        title: str,
        message: str,
        notif_type: str,
        ticket_id: int,
        exclude_user_ids: list[int] | None = None,
    ) -> None:
        recipients = {int(user_id) for user_id in user_ids if user_id is not None}
        exclude = set(exclude_user_ids or [])
        recipients = {user_id for user_id in recipients if user_id not in exclude}
        if not recipients:
            return
        NotificationService(self.db).notify_many(
            user_ids=recipients,
            title=title,
            message=message,
            notif_type=notif_type,
            ticket_id=ticket_id,
        )

    def _notify_roles(
        self,
        roles: list[UserRole],
        title: str,
        message: str,
        notif_type: str,
        ticket_id: int,
        exclude_user_ids: list[int] | None = None,
    ) -> None:
        NotificationService(self.db).notify_roles(
            roles=roles,
            title=title,
            message=message,
            notif_type=notif_type,
            ticket_id=ticket_id,
            exclude_user_ids=exclude_user_ids,
        )

    def _notify_ticket_status_changed(
        self,
        ticket: Ticket,
        current_user: User,
        old_status,
        new_status,
        comment: str | None = None,
    ) -> None:
        old_key = old_status.value if hasattr(old_status, "value") else str(old_status or "")
        new_key = new_status.value if hasattr(new_status, "value") else str(new_status or "")
        actor_id = current_user.id if current_user else None
        staff_roles = [UserRole.ADMIN, UserRole.DISPATCHER]

        if current_user.role == UserRole.EXECUTOR:
            if new_key == TicketStatus.IN_PROGRESS.value:
                self._notify_user_ids(
                    [ticket.author_id],
                    title="Заявка принята в работу",
                    message=f"Исполнитель принял заявку #{ticket.id} в работу.",
                    notif_type="ticket_started",
                    ticket_id=ticket.id,
                    exclude_user_ids=[actor_id],
                )
                self._notify_roles(
                    staff_roles,
                    title="Исполнитель принял заявку",
                    message=f"Заявка #{ticket.id} принята исполнителем в работу.",
                    notif_type="ticket_started",
                    ticket_id=ticket.id,
                    exclude_user_ids=[actor_id],
                )
            elif new_key == TicketStatus.DONE.value:
                self._notify_user_ids(
                    [ticket.author_id],
                    title="Работа по заявке выполнена",
                    message=f"Исполнитель отметил заявку #{ticket.id} как выполненную.",
                    notif_type="ticket_done",
                    ticket_id=ticket.id,
                    exclude_user_ids=[actor_id],
                )
                self._notify_roles(
                    staff_roles,
                    title="Заявка выполнена",
                    message=f"Исполнитель отметил заявку #{ticket.id} как выполненную.",
                    notif_type="ticket_done",
                    ticket_id=ticket.id,
                    exclude_user_ids=[actor_id],
                )
            elif new_key == TicketStatus.CREATED.value and old_key in [
                TicketStatus.ASSIGNED.value,
                TicketStatus.IN_PROGRESS.value,
            ]:
                self._notify_user_ids(
                    [ticket.author_id],
                    title="Исполнитель отказался от заявки",
                    message=f"Заявка #{ticket.id} возвращена диспетчеру для повторного назначения.",
                    notif_type="ticket_executor_rejected",
                    ticket_id=ticket.id,
                    exclude_user_ids=[actor_id],
                )
                self._notify_roles(
                    staff_roles,
                    title="Исполнитель отказался от заявки",
                    message=f"Заявка #{ticket.id} требует повторного назначения.",
                    notif_type="ticket_executor_rejected",
                    ticket_id=ticket.id,
                    exclude_user_ids=[actor_id],
                )
            return

        if current_user.role == UserRole.RESIDENT:
            if new_key == TicketStatus.CLOSED.value:
                self._notify_user_ids(
                    [ticket.executor_id],
                    title="Житель принял работу",
                    message=f"Житель принял работу по заявке #{ticket.id}.",
                    notif_type="ticket_closed",
                    ticket_id=ticket.id,
                    exclude_user_ids=[actor_id],
                )
                self._notify_roles(
                    staff_roles,
                    title="Работа принята жителем",
                    message=f"Житель принял работу по заявке #{ticket.id}.",
                    notif_type="ticket_closed",
                    ticket_id=ticket.id,
                    exclude_user_ids=[actor_id],
                )
            return

        if current_user.role in [UserRole.ADMIN, UserRole.DISPATCHER]:
            if new_key == TicketStatus.CANCELED.value:
                self._notify_user_ids(
                    [ticket.author_id],
                    title="Заявка отклонена",
                    message=f"Заявка #{ticket.id} отклонена сотрудником.",
                    notif_type="ticket_rejected",
                    ticket_id=ticket.id,
                    exclude_user_ids=[actor_id],
                )

    def _ensure_executor_available_today(self, executor_user_id: int) -> None:
        profile = (
            self.db.query(ExecutorProfile)
            .filter(ExecutorProfile.user_id == executor_user_id)
            .first()
        )
        if not profile or not profile.is_active:
            raise HTTPException(status_code=400, detail="Профиль исполнителя неактивен или отсутствует")

        today = moscow_today()

        availability = get_executor_availability_state(profile, target_date=today)
        if availability.has_day_off:
            raise HTTPException(status_code=400, detail="У исполнителя сегодня выходной")

        if not availability.has_schedule:
            raise HTTPException(status_code=400, detail="Исполнитель сегодня недоступен по графику работы")

        if not availability.within_working_hours:
            raise HTTPException(status_code=400, detail="Исполнитель сейчас вне рабочего времени")

    def get_tickets(
        self,
        user: User,
        status: TicketStatus | None = None,
        house_id: int | None = None,
        executor_id: int | None = None,
        priority=None,
        created_from=None,
        created_to=None,
        limit: int = 100,
        skip: int = 0,
        **kwargs,
    ) -> List[Ticket]:
        if user.role in [UserRole.ADMIN, UserRole.DISPATCHER, UserRole.AUDITOR]:
            tickets = self.ticket_repo.get_filtered(
                status=status,
                house_id=house_id,
                executor_id=executor_id,
                created_from=created_from,
                created_to=created_to,
                limit=limit,
                skip=skip,
                overdue_hours=kwargs.get("overdue_hours"),
            )
        elif user.role == UserRole.EXECUTOR:
            tickets = self.ticket_repo.get_filtered(
                executor_id=user.id,
                status=status,
                created_from=created_from,
                created_to=created_to,
                limit=limit,
                skip=skip,
                overdue_hours=kwargs.get("overdue_hours"),
            )
        else:
            tickets = self.ticket_repo.get_for_resident(
                house_id=user.house_id,
                apartment=user.apartment,
                apartment_id=user.apartment_id,
            )

            if status is not None:
                tickets = [ticket for ticket in tickets if ticket.status == status]

        if priority is not None and tickets and hasattr(tickets[0], "priority"):
            priority_value = priority.value if hasattr(priority, "value") else str(priority)
            tickets = [
                ticket
                for ticket in tickets
                if str(getattr(ticket, "priority", "")).lower() == str(priority_value).lower()
            ]

        return tickets

    def get_ticket(self, ticket_id: int, current_user: User) -> Ticket:
        ticket = self._get_ticket_or_404(ticket_id)

        if current_user.role in [UserRole.ADMIN, UserRole.DISPATCHER, UserRole.AUDITOR]:
            return ticket

        if current_user.role == UserRole.EXECUTOR:
            if ticket.executor_id != current_user.id:
                raise HTTPException(status_code=403, detail="Not enough permissions")
            return ticket

        if current_user.role == UserRole.RESIDENT:
            same_house = bool(current_user.house_id is not None and ticket.house_id == current_user.house_id)
            same_apartment = False

            if current_user.apartment_id and ticket.apartment_id:
                same_apartment = ticket.apartment_id == current_user.apartment_id
            elif current_user.apartment and ticket.apartment:
                same_apartment = ticket.apartment == current_user.apartment

            if ticket.author_id == current_user.id or (same_house and same_apartment):
                return ticket

        raise HTTPException(status_code=403, detail="Not enough permissions")

    def create_ticket(self, payload: TicketCreate, user: User) -> Ticket:
        if user.role not in [UserRole.RESIDENT, UserRole.ADMIN, UserRole.DISPATCHER]:
            raise HTTPException(status_code=403, detail="Not enough permissions")

        if user.role == UserRole.RESIDENT:
            self._ensure_resident_not_banned(user)

        ensure_clean_text(payload.title, payload.description, payload.external_contact_phone)

        data = payload.model_dump()
        self._ensure_category_type(data.get("category_id"), "problem", "ticket category")
        self._ensure_category_type(data.get("place_category_id"), "location", "ticket place category")
        raw_priority = data.get("priority")
        if raw_priority is None:
            data["priority"] = TicketPriority.NORMAL
        elif isinstance(raw_priority, TicketPriority):
            data["priority"] = raw_priority
        elif isinstance(raw_priority, str):
            try:
                data["priority"] = TicketPriority(str(raw_priority).strip().lower())
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="Unsupported ticket priority") from exc
        else:
            try:
                data["priority"] = TicketPriority(str(raw_priority).strip().lower())
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="Unsupported ticket priority") from exc

        if user.role == UserRole.RESIDENT:
            data["author_id"] = user.id
            data["is_external_request"] = False
            data["external_contact_phone"] = None

            if user.house_id is not None:
                data["house_id"] = user.house_id

            if user.apartment_id is not None:
                data["apartment_id"] = user.apartment_id

            if user.apartment:
                data["apartment"] = user.apartment

        apartment_id = data.get("apartment_id")
        if apartment_id is not None:
            apartment_obj = (
                self.db.query(Apartment)
                .filter(Apartment.id == apartment_id, Apartment.is_active.is_(True))
                .first()
            )
            if not apartment_obj:
                raise HTTPException(status_code=404, detail="Apartment not found")

            data["house_id"] = apartment_obj.house_id
            if not data.get("apartment"):
                data["apartment"] = apartment_obj.apartment_number

        if user.role in [UserRole.ADMIN, UserRole.DISPATCHER] and data.get("created_for_user_id"):
            resident = self.user_repo.get_by_id(data["created_for_user_id"])
            if not resident or resident.role != UserRole.RESIDENT:
                raise HTTPException(status_code=404, detail="Resident not found")
            data["author_id"] = resident.id
            data["house_id"] = resident.house_id
            data["apartment_id"] = resident.apartment_id
            data["apartment"] = resident.apartment
            data["is_external_request"] = False
            data["external_contact_phone"] = None

        if user.role in [UserRole.ADMIN, UserRole.DISPATCHER] and not data.get("created_for_user_id"):
            if not data.get("house_id"):
                raise HTTPException(status_code=400, detail="Укажите дом для заявки по звонку")
            if not data.get("apartment_id") and not str(data.get("apartment") or "").strip():
                raise HTTPException(status_code=400, detail="Укажите квартиру для заявки по звонку")
            if not str(data.get("external_contact_phone") or "").strip():
                raise HTTPException(status_code=400, detail="Укажите телефон жителя")
            data["author_id"] = user.id
            data["is_external_request"] = True
            data["external_contact_phone"] = str(data.get("external_contact_phone") or "").strip()
            data["show_contact_phone"] = True

        data.pop("created_for_user_id", None)

        ticket = self.ticket_repo.create(data)
        self._add_history(
            ticket.id,
            user_id=user.id,
            new_status=TicketStatus.CREATED.value,
            comment=f"Заявка создана. Создал: {self._format_actor_name(user)}",
        )

        self.db.commit()
        self.db.refresh(ticket)
        self._broadcast_ticket_update(ticket, action="created")
        self._notify_roles(
            [UserRole.ADMIN, UserRole.DISPATCHER],
            title="Новая заявка",
            message=f"Создана заявка #{ticket.id}: {ticket.title}",
            notif_type="ticket_created",
            ticket_id=ticket.id,
            exclude_user_ids=[user.id],
        )
        if ticket.author_id != user.id:
            self._notify_user_ids(
                [ticket.author_id],
                title="Для вас создана заявка",
                message=f"Создана заявка #{ticket.id}: {ticket.title}",
                notif_type="ticket_created_for_resident",
                ticket_id=ticket.id,
                exclude_user_ids=[user.id],
            )
        return ticket

    def upload_file(self, ticket_id: int, file: UploadFile, current_user: User, kind: str | None = None) -> TicketFile:
        ticket = self.get_ticket(ticket_id, current_user)

        if current_user.role == UserRole.RESIDENT:
            self._ensure_resident_not_banned(current_user)
            if ticket.author_id != current_user.id:
                raise HTTPException(status_code=403, detail="You can upload files only to your own ticket")
        elif current_user.role == UserRole.EXECUTOR:
            normalized_kind = str(kind or "").upper()
            if normalized_kind != TicketFileKind.AFTER.value:
                raise HTTPException(status_code=403, detail="Executor can upload only completion photos")
            if ticket.status != TicketStatus.IN_PROGRESS:
                raise HTTPException(status_code=400, detail="Фотоотчёт можно прикрепить только по заявке в работе")

        file_ext = file.filename.split(".")[-1] if file.filename and "." in file.filename else "jpg"
        unique_name = f"{uuid.uuid4()}.{file_ext}"

        dir_path = os.path.join("static", "uploads", "tickets", str(ticket.id))
        os.makedirs(dir_path, exist_ok=True)

        save_path = os.path.join(dir_path, unique_name)
        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        file_kind = TicketFileKind.LEGACY
        if kind:
            normalized_kind = str(kind).upper()
            if normalized_kind in TicketFileKind.__members__:
                file_kind = TicketFileKind[normalized_kind]

        ticket_file = TicketFile(
            ticket_id=ticket.id,
            file_path="/" + save_path.replace("\\", "/"),
            kind=file_kind,
            created_at=datetime.utcnow(),
        )
        self.db.add(ticket_file)
        self.db.commit()
        self.db.refresh(ticket_file)
        self._broadcast_ticket_update(ticket, action="file_uploaded", file_id=ticket_file.id)
        return ticket_file

    def delete_file(self, file_id: int, current_user: User) -> dict:
        ticket_file = self.db.query(TicketFile).filter(TicketFile.id == file_id).first()
        if not ticket_file:
            raise HTTPException(status_code=404, detail="File not found")

        ticket = self.get_ticket(ticket_file.ticket_id, current_user)

        if current_user.role == UserRole.RESIDENT:
            self._ensure_resident_not_banned(current_user)
            if ticket.author_id != current_user.id:
                raise HTTPException(status_code=403, detail="You can delete files only from your own ticket")
        elif current_user.role == UserRole.EXECUTOR:
            file_kind = ticket_file.kind.value if hasattr(ticket_file.kind, "value") else str(ticket_file.kind or "")
            if file_kind.upper() != TicketFileKind.AFTER.value:
                raise HTTPException(status_code=403, detail="Executor can delete only completion photos")
            if ticket.status != TicketStatus.IN_PROGRESS:
                raise HTTPException(status_code=400, detail="Фотоотчёт можно удалить только до отметки заявки выполненной")
            if ticket.started_at and ticket_file.created_at and ticket_file.created_at < ticket.started_at:
                raise HTTPException(
                    status_code=400,
                    detail="Можно удалить только фотоотчёт текущего выполнения заявки",
                )

        disk_path = ticket_file.file_path.lstrip("/").replace("/", os.sep)
        if os.path.exists(disk_path):
            os.remove(disk_path)

        self.db.delete(ticket_file)
        self.db.commit()
        self._broadcast_ticket_update(ticket, action="file_deleted", file_id=file_id)
        return {"status": "ok"}

    def cancel_ticket(self, ticket_id: int, current_user: User, payload: TicketCancelRequest | None = None):
        ticket = self.get_ticket(ticket_id, current_user)

        if current_user.role not in [UserRole.RESIDENT, UserRole.ADMIN, UserRole.DISPATCHER]:
            raise HTTPException(status_code=403, detail="Not enough permissions")

        if current_user.role == UserRole.RESIDENT:
            self._ensure_resident_not_banned(current_user)
            if ticket.author_id != current_user.id:
                raise HTTPException(status_code=403, detail="You can cancel only your own ticket")
            if ticket.status != TicketStatus.CREATED:
                raise HTTPException(status_code=400, detail="Житель может отменить только новую заявку")
            reason_key = (payload.reason if payload else None) or ""
            cancel_reason = self.RESIDENT_CANCEL_REASONS.get(reason_key)
            if not cancel_reason:
                raise HTTPException(status_code=400, detail="Выберите причину отмены заявки")
        else:
            cancel_reason = None
            if ticket.status != TicketStatus.CREATED or ticket.executor_id is not None:
                raise HTTPException(
                    status_code=400,
                    detail="Отклонить можно только новую заявку без назначенного исполнителя",
                )

        old_status = ticket.status
        ticket.status = TicketStatus.CANCELED
        ticket.canceled_at = datetime.utcnow()
        action_label = "отклонена" if current_user.role in [UserRole.ADMIN, UserRole.DISPATCHER] else "отменена"
        reason_line = f" Причина: {cancel_reason}." if cancel_reason else ""
        self._add_history(
            ticket.id,
            user_id=current_user.id,
            old_status=old_status.value if hasattr(old_status, "value") else str(old_status),
            new_status=TicketStatus.CANCELED.value,
            comment=f"Заявка {action_label}.{reason_line} Действие выполнил: {self._format_actor_name(current_user)}",
        )

        self.db.commit()
        self.db.refresh(ticket)
        self._broadcast_ticket_update(ticket, action="canceled")
        if current_user.role == UserRole.RESIDENT:
            self._notify_roles(
                [UserRole.ADMIN, UserRole.DISPATCHER],
                title="Житель отменил заявку",
                message=f"Житель отменил заявку #{ticket.id}.",
                notif_type="ticket_canceled_by_resident",
                ticket_id=ticket.id,
                exclude_user_ids=[current_user.id],
            )
        else:
            self._notify_user_ids(
                [ticket.author_id],
                title="Заявка отклонена",
                message=f"Заявка #{ticket.id} отклонена сотрудником.",
                notif_type="ticket_rejected",
                ticket_id=ticket.id,
                exclude_user_ids=[current_user.id],
            )
        return ticket

    def assign_ticket(self, ticket_id: int, payload: TicketAssign, current_user: User) -> Ticket:
        return self.assign_executor(ticket_id, payload, current_user)

    def assign_executor(self, ticket_id: int, payload: TicketAssign, current_user: User) -> Ticket:
        if current_user.role not in [UserRole.ADMIN, UserRole.DISPATCHER]:
            raise HTTPException(status_code=403, detail="Недостаточно прав")

        ticket = self._get_ticket_or_404(ticket_id)
        old_status = ticket.status
        previous_executor_id = ticket.executor_id

        explicit_unassign = payload.executor_id == 0 or payload.executor_profile_id == 0

        if explicit_unassign:
            if not ticket.executor_id:
                raise HTTPException(status_code=400, detail="На заявке нет назначенного исполнителя")
            if ticket.status != TicketStatus.ASSIGNED:
                raise HTTPException(
                    status_code=400,
                    detail="Снять исполнителя можно только до принятия заявки в работу",
                )
            ticket.executor_id = None
            ticket.status = TicketStatus.CREATED
            ticket.assigned_at = None
            ticket.started_at = None
            self._add_history(
                ticket.id,
                user_id=current_user.id,
                old_status=old_status.value if hasattr(old_status, "value") else str(old_status),
                new_status=ticket.status.value,
                comment=f"Исполнитель снят. Действие выполнил: {self._format_actor_name(current_user)}",
            )
            self.db.commit()
            self.db.refresh(ticket)
            self._broadcast_ticket_update(ticket, action="unassigned")
            self._notify_user_ids(
                [previous_executor_id, ticket.author_id],
                title="Исполнитель снят с заявки",
                message=f"По заявке #{ticket.id} исполнитель снят до принятия в работу.",
                notif_type="ticket_unassigned",
                ticket_id=ticket.id,
                exclude_user_ids=[current_user.id],
            )
            return ticket

        if ticket.status in [TicketStatus.DONE, TicketStatus.CLOSED, TicketStatus.CANCELED]:
            raise HTTPException(status_code=400, detail="Нельзя назначить исполнителя на завершённую заявку")

        if ticket.executor_id:
            raise HTTPException(status_code=400, detail="Исполнитель уже назначен")

        resolved_executor_user_id = None

        if payload.executor_profile_id is not None:
            profile = (
                self.db.query(ExecutorProfile)
                .filter(ExecutorProfile.id == payload.executor_profile_id, ExecutorProfile.is_active.is_(True))
                .first()
            )
            if not profile:
                raise HTTPException(status_code=404, detail="Профиль исполнителя не найден")
            resolved_executor_user_id = profile.user_id
        elif payload.executor_id is not None:
            executor_user = self.user_repo.get_by_id(payload.executor_id)
            if not executor_user or executor_user.role != UserRole.EXECUTOR:
                raise HTTPException(status_code=404, detail="Исполнитель не найден")
            resolved_executor_user_id = executor_user.id
            executor_name = self._format_actor_name(executor_user)
        else:
            raise HTTPException(status_code=400, detail="Нужно указать исполнителя для назначения")

        if payload.executor_profile_id is not None:
            executor_user = self.user_repo.get_by_id(resolved_executor_user_id)
            executor_name = self._format_actor_name(executor_user)

        self._ensure_executor_available_today(resolved_executor_user_id)

        ticket.executor_id = resolved_executor_user_id
        if ticket.status == TicketStatus.CREATED:
            ticket.status = TicketStatus.ASSIGNED
        ticket.assigned_at = datetime.utcnow()
        ticket.started_at = None

        self._add_history(
            ticket.id,
            user_id=current_user.id,
            old_status=old_status.value if hasattr(old_status, "value") else str(old_status),
            new_status=ticket.status.value,
            comment=f"Назначен исполнитель: {executor_name}. Назначил: {self._format_actor_name(current_user)}",
        )

        self.db.commit()
        self.db.refresh(ticket)
        self._broadcast_ticket_update(ticket, action="assigned")
        self._notify_user_ids(
            [resolved_executor_user_id],
            title="Вам назначена заявка",
            message=f"Вам назначена заявка #{ticket.id}: {ticket.title}",
            notif_type="ticket_assigned_to_executor",
            ticket_id=ticket.id,
            exclude_user_ids=[current_user.id],
        )
        self._notify_user_ids(
            [ticket.author_id],
            title="По заявке назначен исполнитель",
            message=f"По заявке #{ticket.id} назначен исполнитель: {executor_name}.",
            notif_type="ticket_assigned_to_resident",
            ticket_id=ticket.id,
            exclude_user_ids=[current_user.id],
        )
        return ticket

    def update_status(self, ticket_id: int, payload: TicketUpdate, current_user: User) -> Ticket:
        ticket = self._get_ticket_or_404(ticket_id)
        old_status = ticket.status
        old_status_key = old_status.value if hasattr(old_status, "value") else str(old_status)
        executor_comment, resident_review = self._split_result_comment(ticket.result_comment)
        history_comment = None

        if current_user.role == UserRole.RESIDENT:
            if ticket.author_id != current_user.id:
                raise HTTPException(status_code=403, detail="Not enough permissions")
            if payload.status != TicketStatus.CLOSED:
                raise HTTPException(status_code=403, detail="Resident can only accept completed work")
            if ticket.status != TicketStatus.DONE:
                raise HTTPException(status_code=400, detail="Only completed ticket can be accepted")
        elif current_user.role == UserRole.EXECUTOR:
            if ticket.executor_id != current_user.id:
                raise HTTPException(status_code=403, detail="Not enough permissions")
        elif current_user.role not in [UserRole.ADMIN, UserRole.DISPATCHER]:
            raise HTTPException(status_code=403, detail="Not enough permissions")

        if payload.status is None:
            raise HTTPException(status_code=400, detail="Status is required")

        ensure_clean_text(payload.comment)

        if current_user.role == UserRole.EXECUTOR:
            comment_text = (payload.comment or "").strip()

            if payload.status == TicketStatus.IN_PROGRESS:
                if old_status != TicketStatus.ASSIGNED:
                    raise HTTPException(status_code=400, detail="В работу можно принять только назначенную заявку")
                if not comment_text:
                    raise HTTPException(
                        status_code=400,
                        detail="Укажите комментарий: когда планируете прийти и возможна ли платная работа",
                    )
                ticket.result_comment = self._compose_result_comment(comment_text, resident_review)
                ticket.started_at = datetime.utcnow()
                history_comment = f"Исполнитель принял заявку в работу. Комментарий: {comment_text}"

            elif payload.status == TicketStatus.CREATED:
                if old_status not in [TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS]:
                    raise HTTPException(status_code=400, detail="Отказаться можно только от назначенной заявки")
                if not comment_text:
                    raise HTTPException(status_code=400, detail="Укажите причину отказа от заявки")
                ticket.executor_id = None
                ticket.assigned_at = None
                ticket.started_at = None
                ticket.done_at = None
                ticket.result_comment = self._compose_result_comment("", resident_review)
                history_comment = f"Исполнитель отказался от заявки. Причина: {comment_text}"

            elif payload.status == TicketStatus.DONE:
                if old_status != TicketStatus.IN_PROGRESS:
                    raise HTTPException(status_code=400, detail="Завершить можно только заявку в работе")
                comment_text = comment_text or "Работа выполнена."
                ticket.result_comment = self._compose_result_comment(comment_text, resident_review)
                ticket.done_at = datetime.utcnow()
                history_comment = f"Исполнитель отметил заявку выполненной. Комментарий: {comment_text}"
                if ticket.is_external_request:
                    payload.status = TicketStatus.CLOSED
                    ticket.closed_at = datetime.utcnow()
                    history_comment = (
                        f"Исполнитель отметил заявку выполненной. Заявка по обращению без профиля жителя закрыта автоматически. "
                        f"Комментарий: {comment_text}"
                    )

            else:
                raise HTTPException(status_code=403, detail="Исполнитель не может установить этот статус")

        ticket.status = payload.status

        if current_user.role == UserRole.RESIDENT and payload.status == TicketStatus.CLOSED:
            if ticket.is_external_request:
                raise HTTPException(status_code=400, detail="Заявка оформлена диспетчером без профиля жителя и не требует принятия работы")
            review_text = (payload.comment or "").strip() or "Работа принята. Претензий нет."
            ticket.result_comment = self._compose_result_comment(executor_comment, review_text)
            ticket.closed_at = datetime.utcnow()
        elif payload.comment and current_user.role != UserRole.EXECUTOR:
            comment_text = payload.comment.strip()
            ticket.result_comment = comment_text

        if current_user.role in [UserRole.ADMIN, UserRole.DISPATCHER]:
            if payload.status == TicketStatus.ASSIGNED and ticket.assigned_at is None:
                ticket.assigned_at = datetime.utcnow()
            elif payload.status == TicketStatus.IN_PROGRESS:
                ticket.started_at = datetime.utcnow()
            elif payload.status == TicketStatus.DONE:
                ticket.done_at = datetime.utcnow()
            elif payload.status == TicketStatus.CANCELED:
                ticket.canceled_at = datetime.utcnow()
            elif payload.status == TicketStatus.CLOSED:
                ticket.closed_at = datetime.utcnow()

        self._add_history(
            ticket.id,
            user_id=current_user.id,
            old_status=old_status_key,
            new_status=payload.status.value if hasattr(payload.status, "value") else str(payload.status),
            comment=history_comment or payload.comment or f"Статус заявки обновлён. Действие выполнил: {self._format_actor_name(current_user)}",
        )

        self.db.commit()
        self.db.refresh(ticket)
        self._broadcast_ticket_update(ticket, action="status_updated")
        self._notify_ticket_status_changed(
            ticket=ticket,
            current_user=current_user,
            old_status=old_status,
            new_status=payload.status,
            comment=history_comment or payload.comment,
        )
        return ticket
