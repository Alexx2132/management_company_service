from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.user import UserRole
from app.repositories.notification_repository import NotificationRepository
from app.services.live_update_hub import live_update_hub
from app.services.push_notification_service import PushNotificationService


class NotificationService:
    def __init__(self, db: Session):
        self.repo = NotificationRepository(db)
        self.db = db

    def notify_user(
        self,
        user_id: int,
        title: str,
        message: str,
        notif_type: str,
        ticket_id: int | None = None,
        complaint_id: int | None = None,
        announcement_id: int | None = None,
        ban_conversation_id: int | None = None,
        message_conversation_id: int | None = None,
        extra_data: dict | None = None,
    ) -> Notification:
        obj = Notification(
            user_id=user_id,
            title=title,
            message=message,
            notif_type=notif_type,
            ticket_id=ticket_id,
            complaint_id=complaint_id,
            announcement_id=announcement_id,
            ban_conversation_id=ban_conversation_id,
            message_conversation_id=message_conversation_id,
            is_read=False,
            created_at=datetime.utcnow(),
        )
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        self._send_push(
            [user_id],
            title=title,
            message=message,
            notif_type=notif_type,
            ticket_id=ticket_id,
            complaint_id=complaint_id,
            announcement_id=announcement_id,
            ban_conversation_id=ban_conversation_id,
            message_conversation_id=message_conversation_id,
            notification_id=obj.id,
            extra_data=extra_data,
        )
        return obj

    def notify_many(
        self,
        user_ids: list[int] | set[int],
        title: str,
        message: str,
        notif_type: str,
        ticket_id: int | None = None,
        complaint_id: int | None = None,
        announcement_id: int | None = None,
        ban_conversation_id: int | None = None,
        message_conversation_id: int | None = None,
        exclude_user_ids: list[int] | None = None,
        extra_data: dict | None = None,
    ) -> int:
        exclude = set(exclude_user_ids or [])
        unique_user_ids = {int(user_id) for user_id in user_ids if user_id is not None}
        target_ids = [user_id for user_id in unique_user_ids if user_id not in exclude]

        if not target_ids:
            return 0

        now = datetime.utcnow()
        for user_id in target_ids:
            self.db.add(
                Notification(
                    user_id=user_id,
                    title=title,
                    message=message,
                    notif_type=notif_type,
                    ticket_id=ticket_id,
                    complaint_id=complaint_id,
                    announcement_id=announcement_id,
                    ban_conversation_id=ban_conversation_id,
                    message_conversation_id=message_conversation_id,
                    is_read=False,
                    created_at=now,
                )
            )

        self.db.commit()
        self._send_push(
            target_ids,
            title=title,
            message=message,
            notif_type=notif_type,
            ticket_id=ticket_id,
            complaint_id=complaint_id,
            announcement_id=announcement_id,
            ban_conversation_id=ban_conversation_id,
            message_conversation_id=message_conversation_id,
            extra_data=extra_data,
        )
        return len(target_ids)

    def notify_roles(
        self,
        roles: list[UserRole],
        title: str,
        message: str,
        notif_type: str,
        ticket_id: int | None = None,
        complaint_id: int | None = None,
        announcement_id: int | None = None,
        ban_conversation_id: int | None = None,
        message_conversation_id: int | None = None,
        exclude_user_ids: list[int] | None = None,
        extra_data: dict | None = None,
    ) -> int:
        exclude_user_ids = exclude_user_ids or []
        from app.models.user import User

        users = self.db.query(User).filter(User.role.in_(roles)).all()
        user_ids = [u.id for u in users if u.id not in exclude_user_ids]
        return self.notify_many(
            user_ids=user_ids,
            title=title,
            message=message,
            notif_type=notif_type,
            ticket_id=ticket_id,
            complaint_id=complaint_id,
            announcement_id=announcement_id,
            ban_conversation_id=ban_conversation_id,
            message_conversation_id=message_conversation_id,
            extra_data=extra_data,
        )

    def list_my(
        self,
        user_id: int,
        unread_only: bool = False,
        skip: int = 0,
        limit: int = 50,
        notif_type: str | None = None,
    ):
        return self.repo.list_for_user(
            user_id=user_id,
            unread_only=unread_only,
            skip=skip,
            limit=limit,
            notif_type=notif_type,
        )

    def get_summary(self, user_id: int) -> dict:
        return {
            "total": self.repo.count_for_user(user_id, unread_only=False),
            "unread": self.repo.count_for_user(user_id, unread_only=True),
            "unread_by_type": self.repo.unread_by_type_for_user(user_id),
        }

    def mark_read(self, user_id: int, notification_id: int) -> Notification:
        obj = self.repo.get_by_id(notification_id)
        if not obj or obj.user_id != user_id:
            raise HTTPException(status_code=404, detail="Notification not found")

        if not obj.is_read:
            obj.is_read = True
            obj.read_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(obj)
        return obj

    def mark_all_read(self, user_id: int) -> int:
        q = self.db.query(Notification).filter(Notification.user_id == user_id, Notification.is_read == False)  # noqa: E712
        updated = q.update({
            Notification.is_read: True,
            Notification.read_at: datetime.utcnow(),
        })
        self.db.commit()
        return int(updated)

    def mark_ban_conversation_read(self, user_id: int, conversation_id: int) -> int:
        updated = (
            self.db.query(Notification)
            .filter(
                Notification.user_id == user_id,
                Notification.ban_conversation_id == conversation_id,
                Notification.notif_type.in_(["ban_message_admin", "ban_message_resident"]),
                Notification.is_read == False,  # noqa: E712
            )
            .update({
                Notification.is_read: True,
                Notification.read_at: datetime.utcnow(),
            }, synchronize_session=False)
        )
        self.db.commit()
        if updated:
            live_update_hub.broadcast_from_sync({
                "entity": "notification",
                "action": "read",
                "kind": "ban_appeal",
                "conversation_id": conversation_id,
                "user_id": user_id,
            })
        return int(updated)

    def mark_message_conversation_read(self, user_id: int, conversation_id: int) -> int:
        updated = (
            self.db.query(Notification)
            .filter(
                Notification.user_id == user_id,
                Notification.message_conversation_id == conversation_id,
                Notification.notif_type.in_(["message_new", "message_new_silent"]),
                Notification.is_read == False,  # noqa: E712
            )
            .update({
                Notification.is_read: True,
                Notification.read_at: datetime.utcnow(),
            }, synchronize_session=False)
        )
        self.db.commit()
        if updated:
            live_update_hub.broadcast_from_sync({
                "entity": "notification",
                "action": "read",
                "kind": "message",
                "conversation_id": conversation_id,
                "user_id": user_id,
            })
        return int(updated)

    def mark_ticket_created_read_for_staff(self, ticket_id: int) -> int:
        updated = (
            self.db.query(Notification)
            .filter(
                Notification.ticket_id == ticket_id,
                Notification.notif_type == "ticket_created",
                Notification.is_read == False,  # noqa: E712
            )
            .update({
                Notification.is_read: True,
                Notification.read_at: datetime.utcnow(),
            }, synchronize_session=False)
        )
        self.db.commit()
        if updated:
            live_update_hub.broadcast_from_sync({
                "entity": "notification",
                "action": "read",
                "kind": "ticket_created",
                "ticket_id": ticket_id,
            })
        return int(updated)

    def _send_push(
        self,
        user_ids: list[int] | set[int],
        title: str,
        message: str,
        notif_type: str,
        ticket_id: int | None = None,
        complaint_id: int | None = None,
        announcement_id: int | None = None,
        notification_id: int | None = None,
        ban_conversation_id: int | None = None,
        message_conversation_id: int | None = None,
        extra_data: dict | None = None,
    ) -> None:
        data = {
            "notif_type": notif_type,
            "ticket_id": ticket_id,
            "complaint_id": complaint_id,
            "announcement_id": announcement_id,
            "notification_id": notification_id,
            "ban_conversation_id": ban_conversation_id,
            "message_conversation_id": message_conversation_id,
        }
        if extra_data:
            data.update(extra_data)
        PushNotificationService(self.db).send_to_users(
            user_ids=user_ids,
            title=title,
            message=message,
            data=data,
        )
