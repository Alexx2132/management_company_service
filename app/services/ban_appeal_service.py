from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.profanity import ensure_clean_text
from app.models.ban_appeal import BanConversation, BanMessage
from app.models.user import User, UserRole
from app.schemas.ban_appeal import BanMessageCreate
from app.services.live_update_hub import live_update_hub
from app.services.notification_service import NotificationService


class BanAppealService:
    def __init__(self, db: Session):
        self.db = db

    def _get_or_create_for_resident(self, resident: User) -> BanConversation:
        if resident.role != UserRole.RESIDENT:
            raise HTTPException(status_code=403, detail="Переписка по блокировке доступна только жителю")

        conversation = (
            self.db.query(BanConversation)
            .options(joinedload(BanConversation.messages).joinedload(BanMessage.sender))
            .filter(BanConversation.resident_id == resident.id)
            .first()
        )
        if conversation:
            return conversation

        conversation = BanConversation(
            resident_id=resident.id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        return conversation

    def get_my_conversation(self, user: User) -> BanConversation:
        conversation = self._get_or_create_for_resident(user)
        NotificationService(self.db).mark_ban_conversation_read(user.id, conversation.id)
        return conversation

    def list_conversations(self, user: User) -> list[BanConversation]:
        if user.role != UserRole.ADMIN:
            raise HTTPException(status_code=403, detail="Переписку по блокировкам может просматривать только администратор")
        return (
            self.db.query(BanConversation)
            .options(
                joinedload(BanConversation.resident),
                joinedload(BanConversation.messages).joinedload(BanMessage.sender),
            )
            .order_by(BanConversation.updated_at.desc())
            .all()
        )

    def get_conversation(self, conversation_id: int, user: User) -> BanConversation:
        query = (
            self.db.query(BanConversation)
            .options(
                joinedload(BanConversation.resident),
                joinedload(BanConversation.messages).joinedload(BanMessage.sender),
            )
            .filter(BanConversation.id == conversation_id)
        )
        conversation = query.first()
        if not conversation:
            raise HTTPException(status_code=404, detail="Переписка не найдена")

        if user.role == UserRole.ADMIN or conversation.resident_id == user.id:
            NotificationService(self.db).mark_ban_conversation_read(user.id, conversation.id)
            return conversation
        raise HTTPException(status_code=403, detail="Нет доступа к этой переписке")

    def add_message_to_my_conversation(self, payload: BanMessageCreate, user: User) -> BanConversation:
        conversation = self._get_or_create_for_resident(user)
        return self._add_message(conversation, payload, user)

    def add_message(self, conversation_id: int, payload: BanMessageCreate, user: User) -> BanConversation:
        conversation = self.get_conversation(conversation_id, user)
        if user.role != UserRole.ADMIN and conversation.resident_id != user.id:
            raise HTTPException(status_code=403, detail="Нет доступа к этой переписке")
        return self._add_message(conversation, payload, user)

    def _add_message(self, conversation: BanConversation, payload: BanMessageCreate, sender: User) -> BanConversation:
        if sender.role == UserRole.ADMIN:
            resident = conversation.resident or self.db.query(User).filter(User.id == conversation.resident_id).first()
            if not resident or resident.banned_until is None or resident.banned_until <= datetime.utcnow():
                raise HTTPException(
                    status_code=400,
                    detail="Житель уже разблокирован, переписка по ограничению закрыта",
                )

        text = payload.message.strip()
        ensure_clean_text(text)
        if not text:
            raise HTTPException(status_code=400, detail="Введите сообщение")

        message = BanMessage(
            conversation_id=conversation.id,
            sender_id=sender.id,
            message=text,
            created_at=datetime.utcnow(),
        )
        conversation.updated_at = datetime.utcnow()
        self.db.add(message)
        self.db.commit()

        if sender.role == UserRole.ADMIN:
            NotificationService(self.db).notify_user(
                user_id=conversation.resident_id,
                title="Ответ администратора по блокировке",
                message="Администратор ответил в переписке по блокировке.",
                notif_type="ban_message_resident",
                ban_conversation_id=conversation.id,
            )
        else:
            NotificationService(self.db).notify_roles(
                roles=[UserRole.ADMIN],
                title="Новое сообщение по блокировке",
                message=f"Житель отправил сообщение по блокировке: {text[:120]}",
                notif_type="ban_message_admin",
                ban_conversation_id=conversation.id,
                exclude_user_ids=[sender.id],
            )

        live_update_hub.broadcast_from_sync({
            "entity": "ban_appeal",
            "action": "message_created",
            "conversation_id": conversation.id,
            "resident_id": conversation.resident_id,
            "sender_id": sender.id,
        })

        return self.get_conversation(conversation.id, sender)
