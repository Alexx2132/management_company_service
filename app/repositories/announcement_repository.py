from sqlalchemy import or_
from sqlalchemy.orm import Session
from typing import List

from app.repositories.base import BaseRepository
from app.models.announcement import Announcement
from app.models.user import User


class AnnouncementRepository(BaseRepository[Announcement]):
    def __init__(self, db: Session):
        super().__init__(Announcement, db)

    def get_visible_for_user(self, user: User) -> List[Announcement]:
        # Логика: если у юзера нет дома, и он не админ -> только общие
        user_house_id = user.house_id

        if user.role == "admin":
            return self.get_all()

        if user_house_id is None:
            # Показываем только те, где target_house_id IS NULL
            return self.db.query(Announcement).filter(
                Announcement.target_house_id == None
            ).all()

        # Иначе: Общие ИЛИ Для моего дома
        return self.db.query(Announcement).filter(
            or_(
                Announcement.target_house_id == None,
                Announcement.target_house_id == user_house_id
            )
        ).order_by(Announcement.created_at.desc()).all()
