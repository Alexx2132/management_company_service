from typing import List

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models.announcement import Announcement
from app.models.location import Apartment
from app.models.user import User, UserRole
from app.repositories.base import BaseRepository
from app.services.permissions import is_staff_like


class AnnouncementRepository(BaseRepository[Announcement]):
    def __init__(self, db: Session):
        super().__init__(Announcement, db)

    def get_visible_for_user(self, user: User) -> List[Announcement]:
        query = self.db.query(Announcement)

        if not is_staff_like(user):
            query = query.filter(Announcement.is_active == True)

        if is_staff_like(user):
            return query.order_by(Announcement.created_at.desc()).all()

        if user.house_id is None:
            return (
                query
                .filter(
                    Announcement.target_house_id == None,
                    Announcement.target_entrance_id == None
                )
                .order_by(Announcement.created_at.desc())
                .all()
            )

        resident_entrance_id = None
        if getattr(user, "apartment_ref", None) and user.apartment_ref.entrance_id:
            resident_entrance_id = user.apartment_ref.entrance_id
        elif user.apartment_id:
            apartment = (
                self.db.query(Apartment)
                .filter(Apartment.id == user.apartment_id)
                .first()
            )
            resident_entrance_id = apartment.entrance_id if apartment else None

        query = query.filter(
            or_(
                and_(
                    Announcement.target_house_id == None,
                    Announcement.target_entrance_id == None
                ),
                and_(
                    Announcement.target_house_id == user.house_id,
                    Announcement.target_entrance_id == None
                ),
                and_(
                    Announcement.target_house_id == user.house_id,
                    Announcement.target_entrance_id == resident_entrance_id
                )
            )
        )

        return query.order_by(Announcement.created_at.desc()).all()
