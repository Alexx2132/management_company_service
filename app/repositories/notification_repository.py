from collections import defaultdict

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.repositories.base import BaseRepository


class NotificationRepository(BaseRepository[Notification]):
    def __init__(self, db: Session):
        super().__init__(Notification, db)

    def list_for_user(
        self,
        user_id: int,
        unread_only: bool = False,
        skip: int = 0,
        limit: int = 50,
        notif_type: str | None = None,
    ):
        q = self.db.query(Notification).filter(Notification.user_id == user_id)
        if unread_only:
            q = q.filter(Notification.is_read == False)  # noqa: E712
        if notif_type:
            q = q.filter(Notification.notif_type == notif_type)
        return q.order_by(desc(Notification.created_at)).offset(skip).limit(limit).all()

    def count_for_user(self, user_id: int, unread_only: bool = False) -> int:
        q = self.db.query(func.count(Notification.id)).filter(Notification.user_id == user_id)
        if unread_only:
            q = q.filter(Notification.is_read == False)  # noqa: E712
        return int(q.scalar() or 0)

    def unread_by_type_for_user(self, user_id: int) -> dict[str, int]:
        rows = (
            self.db.query(Notification.notif_type, func.count(Notification.id))
            .filter(Notification.user_id == user_id, Notification.is_read == False)  # noqa: E712
            .group_by(Notification.notif_type)
            .all()
        )
        result: dict[str, int] = defaultdict(int)
        for notif_type, count in rows:
            result[str(notif_type)] = int(count or 0)
        return dict(result)