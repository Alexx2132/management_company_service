from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.profanity import ensure_clean_text
from app.models.location import Apartment
from app.models.message import Message, MessageConversation, MessageParticipant
from app.models.notification import Notification
from app.models.ticket import Ticket
from app.models.ticket_complaint import ComplaintComment, ComplaintType, TicketComplaint
from app.models.user import User, UserRole
from app.schemas.message import MessageConversationCreate, MessageCreate, MessageMuteRequest
from app.services.live_update_hub import live_update_hub
from app.services.notification_service import NotificationService


STAFF_ROLES = {UserRole.ADMIN, UserRole.ADMIN_ASSISTANT, UserRole.DISPATCHER, UserRole.AUDITOR}


class MessageService:
    def __init__(self, db: Session):
        self.db = db
        self.notifications = NotificationService(db)

    def list_conversations(self, user: User) -> list[dict]:
        conversations = (
            self._base_query()
            .join(MessageParticipant)
            .filter(MessageParticipant.user_id == user.id)
            .order_by(MessageConversation.updated_at.desc())
            .all()
        )
        return [self._serialize_conversation(conversation, user) for conversation in conversations]

    def get_conversation(self, conversation_id: int, user: User, mark_read: bool = True) -> dict:
        conversation = self._get_conversation_or_404(conversation_id)
        self._ensure_participant(conversation, user)
        if mark_read:
            self.mark_read(conversation.id, user)
            conversation = self._get_conversation_or_404(conversation_id)
        return self._serialize_conversation(conversation, user)

    def create_or_get_conversation(self, payload: MessageConversationCreate, user: User) -> dict:
        target = self._get_user_or_404(payload.participant_id)
        if target.id == user.id:
            raise HTTPException(status_code=400, detail="Нельзя создать переписку с самим собой")

        ticket = None
        if payload.ticket_id:
            ticket = self.db.query(Ticket).filter(Ticket.id == payload.ticket_id).first()
            if not ticket:
                raise HTTPException(status_code=404, detail="Заявка не найдена")

        if not self._can_contact(user, target, ticket):
            raise HTTPException(status_code=403, detail="Нет доступа к переписке с этим пользователем")

        direct_key = self._direct_key(user.id, target.id)
        conversation = self._base_query().filter(MessageConversation.direct_key == direct_key).first()
        if conversation:
            return self._serialize_conversation(conversation, user)

        now = datetime.utcnow()
        conversation = MessageConversation(
            context_type="ticket" if ticket else "direct",
            direct_key=direct_key,
            ticket_id=ticket.id if ticket else None,
            created_by_id=user.id,
            created_at=now,
            updated_at=now,
        )
        self.db.add(conversation)
        self.db.flush()
        self.db.add_all([
            MessageParticipant(conversation_id=conversation.id, user_id=user.id, last_read_at=now),
            MessageParticipant(conversation_id=conversation.id, user_id=target.id),
        ])
        self.db.commit()
        return self.get_conversation(conversation.id, user, mark_read=False)

    def create_or_get_admin_conversation(self, user: User) -> dict:
        if user.role != UserRole.RESIDENT:
            raise HTTPException(status_code=403, detail="Переписка с администратором доступна жителю")

        target = (
            self.db.query(User)
            .filter(User.role == UserRole.ADMIN, User.id != user.id)
            .order_by(User.id.asc())
            .first()
        )
        if not target:
            target = (
                self.db.query(User)
                .filter(User.role == UserRole.ADMIN_ASSISTANT, User.id != user.id)
                .order_by(User.id.asc())
                .first()
            )
        if not target:
            raise HTTPException(status_code=404, detail="Администратор для переписки не найден")

        return self.create_or_get_conversation(MessageConversationCreate(participant_id=target.id), user)

    def create_message(self, conversation_id: int, payload: MessageCreate, user: User) -> dict:
        conversation = self._get_conversation_or_404(conversation_id)
        self._ensure_participant(conversation, user)
        if conversation.is_closed:
            raise HTTPException(status_code=400, detail="Переписка закрыта")

        body = payload.body.strip()
        ensure_clean_text(body)
        if not body:
            raise HTTPException(status_code=400, detail="Введите сообщение")

        now = datetime.utcnow()
        message = Message(
            conversation_id=conversation.id,
            sender_id=user.id,
            body=body,
            created_at=now,
        )
        conversation.updated_at = now
        for participant in conversation.participants:
            if participant.user_id == user.id:
                participant.last_read_at = now

        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)

        self._notify_message(conversation.id, message, user)
        live_update_hub.broadcast_from_sync({
            "entity": "message",
            "action": "created",
            "conversation_id": conversation.id,
            "sender_id": user.id,
        })
        return self.get_conversation(conversation.id, user, mark_read=False)

    def mark_read(self, conversation_id: int, user: User) -> dict:
        conversation = self._get_conversation_or_404(conversation_id)
        participant = self._ensure_participant(conversation, user)
        participant.last_read_at = datetime.utcnow()
        self.db.commit()
        self.notifications.mark_message_conversation_read(user.id, conversation.id)
        return self._serialize_conversation(conversation, user)

    def mute(self, conversation_id: int, payload: MessageMuteRequest, user: User) -> dict:
        conversation = self._get_conversation_or_404(conversation_id)
        participant = self._ensure_participant(conversation, user)
        participant.muted_until = (
            None if payload.minutes is None or payload.minutes <= 0
            else datetime.utcnow() + timedelta(minutes=payload.minutes)
        )
        self.db.commit()
        self.db.refresh(conversation)
        return self._serialize_conversation(conversation, user)

    def list_contacts(self, user: User, role: str | None = None, q: str | None = None) -> list[dict]:
        allowed = self._allowed_contact_users(user)
        if role:
            allowed = [item for item in allowed if item["user"].role.value == role]

        query = (q or "").strip().lower()
        if query:
            allowed = [
                item for item in allowed
                if query in (item["user"].full_name or "").lower()
                or query in (item["user"].login or "").lower()
                or query in (item["user"].contact_phone or "").lower()
            ]

        result = []
        seen: set[tuple[int, int | None]] = set()
        for item in allowed:
            target = item["user"]
            ticket_id = item.get("ticket_id")
            key = (target.id, ticket_id)
            if target.id == user.id or key in seen:
                continue
            seen.add(key)
            result.append(self._contact_payload(target, ticket_id=ticket_id, reason=item.get("reason")))
        return result

    def _base_query(self):
        return self.db.query(MessageConversation).options(
            selectinload(MessageConversation.participants)
            .joinedload(MessageParticipant.user)
            .joinedload(User.house),
            selectinload(MessageConversation.participants)
            .joinedload(MessageParticipant.user)
            .joinedload(User.apartment_ref)
            .joinedload(Apartment.entrance),
            selectinload(MessageConversation.messages)
            .joinedload(Message.sender)
            .joinedload(User.house),
            selectinload(MessageConversation.messages)
            .joinedload(Message.sender)
            .joinedload(User.apartment_ref)
            .joinedload(Apartment.entrance),
            selectinload(MessageConversation.messages)
            .selectinload(Message.files),
            joinedload(MessageConversation.ticket),
        )

    def _get_conversation_or_404(self, conversation_id: int) -> MessageConversation:
        conversation = self._base_query().filter(MessageConversation.id == conversation_id).first()
        if not conversation:
            raise HTTPException(status_code=404, detail="Переписка не найдена")
        return conversation

    def _get_user_or_404(self, user_id: int) -> User:
        user = (
            self.db.query(User)
            .options(joinedload(User.house), joinedload(User.apartment_ref).joinedload(Apartment.entrance))
            .filter(User.id == user_id)
            .first()
        )
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь для переписки не найден")
        return user

    def _ensure_participant(self, conversation: MessageConversation, user: User) -> MessageParticipant:
        participant = next((item for item in conversation.participants if item.user_id == user.id), None)
        if not participant:
            raise HTTPException(status_code=403, detail="Нет доступа к этой переписке")
        return participant

    def _serialize_conversation(self, conversation: MessageConversation, user: User) -> dict:
        current_participant = next((item for item in conversation.participants if item.user_id == user.id), None)
        return {
            "id": conversation.id,
            "title": self._conversation_title(conversation, user),
            "context_type": conversation.context_type,
            "ticket_id": conversation.ticket_id,
            "created_by_id": conversation.created_by_id,
            "is_closed": conversation.is_closed,
            "unread_count": self._unread_count(user.id, conversation.id),
            "muted_until": current_participant.muted_until if current_participant else None,
            "created_at": conversation.created_at,
            "updated_at": conversation.updated_at,
            "participants": conversation.participants,
            "messages": conversation.messages,
        }

    def _conversation_title(self, conversation: MessageConversation, user: User) -> str:
        others = [item.user for item in conversation.participants if item.user_id != user.id and item.user]
        if others:
            return ", ".join(item.full_name for item in others[:3])
        return conversation.title or "Переписка"

    def _unread_count(self, user_id: int, conversation_id: int) -> int:
        return int(
            self.db.query(func.count(Notification.id))
            .filter(
                Notification.user_id == user_id,
                Notification.message_conversation_id == conversation_id,
                Notification.notif_type.in_(["message_new", "message_new_silent"]),
                Notification.is_read == False,  # noqa: E712
            )
            .scalar()
            or 0
        )

    def _notify_message(self, conversation_id: int, message: Message, sender: User) -> None:
        conversation = self._get_conversation_or_404(conversation_id)
        for participant in conversation.participants:
            if participant.user_id == sender.id:
                continue
            muted = participant.muted_until is not None and participant.muted_until > datetime.utcnow()
            self.notifications.notify_user(
                user_id=participant.user_id,
                title="Новое сообщение",
                message=f"{sender.full_name}: {message.body[:160]}",
                notif_type="message_new_silent" if muted else "message_new",
                message_conversation_id=conversation.id,
                ticket_id=conversation.ticket_id,
                extra_data={"silent": "true" if muted else "false"},
            )

    def _can_contact(self, user: User, target: User, ticket: Ticket | None = None) -> bool:
        if user.role in STAFF_ROLES:
            return True
        if user.role == UserRole.EXECUTOR:
            if target.role in STAFF_ROLES:
                return True
            if target.role == UserRole.RESIDENT:
                query = self.db.query(Ticket).filter(Ticket.executor_id == user.id, Ticket.author_id == target.id)
                if ticket:
                    query = query.filter(Ticket.id == ticket.id)
                return self.db.query(query.exists()).scalar()
            return False
        if user.role == UserRole.RESIDENT:
            if target.role in {UserRole.ADMIN, UserRole.ADMIN_ASSISTANT}:
                return True
            if target.role == UserRole.EXECUTOR:
                query = self.db.query(Ticket).filter(Ticket.author_id == user.id, Ticket.executor_id == target.id)
                if ticket:
                    query = query.filter(Ticket.id == ticket.id)
                return self.db.query(query.exists()).scalar()
            if target.role == UserRole.DISPATCHER:
                query = self.db.query(Ticket).filter(Ticket.author_id == user.id)
                if ticket:
                    query = query.filter(Ticket.id == ticket.id)
                return self.db.query(query.exists()).scalar()
            if target.role == UserRole.AUDITOR:
                return self._resident_can_contact_auditor(user.id, target.id, ticket.id if ticket else None)
        return False

    def _resident_can_contact_auditor(self, resident_id: int, auditor_id: int, ticket_id: int | None = None) -> bool:
        filters = [
            TicketComplaint.author_id == resident_id,
            TicketComplaint.complaint_type == ComplaintType.DISPATCHER_INACTION,
        ]
        if ticket_id:
            filters.append(TicketComplaint.ticket_id == ticket_id)

        resolved_by_auditor = (
            self.db.query(TicketComplaint.id)
            .filter(*filters, TicketComplaint.resolver_id == auditor_id)
            .first()
        )
        if resolved_by_auditor:
            return True

        commented_by_auditor = (
            self.db.query(TicketComplaint.id)
            .join(ComplaintComment, ComplaintComment.complaint_id == TicketComplaint.id)
            .filter(*filters, ComplaintComment.author_id == auditor_id)
            .first()
        )
        return commented_by_auditor is not None

    def _allowed_contact_users(self, user: User) -> list[dict]:
        if user.role in STAFF_ROLES:
            users = (
                self.db.query(User)
                .options(joinedload(User.house), joinedload(User.apartment_ref).joinedload(Apartment.entrance))
                .filter(User.id != user.id)
                .order_by(User.role, User.full_name)
                .limit(300)
                .all()
            )
            return [{"user": item, "reason": "Доступен для служебной переписки"} for item in users]

        if user.role == UserRole.EXECUTOR:
            result = []
            staff = (
                self.db.query(User)
                .options(joinedload(User.house), joinedload(User.apartment_ref).joinedload(Apartment.entrance))
                .filter(User.role.in_([UserRole.ADMIN, UserRole.ADMIN_ASSISTANT, UserRole.DISPATCHER, UserRole.AUDITOR]))
                .all()
            )
            result.extend({"user": item, "reason": "Сотрудник сервиса"} for item in staff)

            tickets = (
                self.db.query(Ticket)
                .options(
                    joinedload(Ticket.author).joinedload(User.house),
                    joinedload(Ticket.author).joinedload(User.apartment_ref).joinedload(Apartment.entrance),
                )
                .filter(Ticket.executor_id == user.id)
                .all()
            )
            for ticket in tickets:
                if ticket.author:
                    result.append({"user": ticket.author, "ticket_id": ticket.id, "reason": f"Житель по заявке #{ticket.id}"})
            return result

        if user.role == UserRole.RESIDENT:
            result = []
            admins = (
                self.db.query(User)
                .options(joinedload(User.house), joinedload(User.apartment_ref).joinedload(Apartment.entrance))
                .filter(User.role.in_([UserRole.ADMIN, UserRole.ADMIN_ASSISTANT]))
                .all()
            )
            result.extend({"user": item, "reason": "Администрация сервиса"} for item in admins)

            tickets = (
                self.db.query(Ticket)
                .options(joinedload(Ticket.executor))
                .filter(Ticket.author_id == user.id)
                .all()
            )
            if tickets:
                dispatchers = (
                    self.db.query(User)
                    .options(joinedload(User.house), joinedload(User.apartment_ref).joinedload(Apartment.entrance))
                    .filter(User.role == UserRole.DISPATCHER)
                    .all()
                )
                result.extend({"user": item, "reason": "Диспетчер по заявкам"} for item in dispatchers)

            for ticket in tickets:
                if ticket.executor:
                    result.append({"user": ticket.executor, "ticket_id": ticket.id, "reason": f"Исполнитель по заявке #{ticket.id}"})

            regulatory_complaints = (
                self.db.query(TicketComplaint)
                .options(
                    joinedload(TicketComplaint.resolver),
                    joinedload(TicketComplaint.comments).joinedload(ComplaintComment.author),
                )
                .filter(
                    TicketComplaint.author_id == user.id,
                    TicketComplaint.complaint_type == ComplaintType.DISPATCHER_INACTION,
                )
                .all()
            )
            for complaint in regulatory_complaints:
                candidates = []
                if complaint.resolver and complaint.resolver.role == UserRole.AUDITOR:
                    candidates.append(complaint.resolver)
                candidates.extend(
                    comment.author for comment in complaint.comments
                    if comment.author and comment.author.role == UserRole.AUDITOR
                )
                for auditor in candidates:
                    result.append({
                        "user": auditor,
                        "ticket_id": complaint.ticket_id,
                        "reason": f"Контролирующий орган по обращению #{complaint.id}",
                    })
            return result

        return []

    def _contact_payload(self, user: User, ticket_id: int | None = None, reason: str | None = None) -> dict:
        return {
            "id": user.id,
            "full_name": user.full_name,
            "role": user.role.value,
            "login": user.login,
            "contact_phone": user.contact_phone,
            "house_address": user.house_address,
            "entrance_number": user.entrance_number,
            "apartment_number": user.apartment_number,
            "ticket_id": ticket_id,
            "reason": reason,
        }

    @staticmethod
    def _direct_key(first_user_id: int, second_user_id: int) -> str:
        left, right = sorted([int(first_user_id), int(second_user_id)])
        return f"{left}:{right}"
