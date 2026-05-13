from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.house_info import EmergencyContact, HouseEvent, HouseSchedule
from app.models.user import User, UserRole
from app.schemas.house_info import (
    EmergencyContactCreate,
    HouseEventCreate,
    HouseScheduleCreate,
)
from app.services.permissions import can_manage_house_info, is_admin


class HouseInfoService:
    def __init__(self, db: Session):
        self.db = db

    def _ensure_write_access(self, user: User) -> None:
        if can_manage_house_info(user):
            return
        raise HTTPException(status_code=403, detail="Not enough permissions")

    def _can_manage(self, user: User, author_id: int) -> bool:
        if is_admin(user):
            return True
        if user.role == UserRole.DISPATCHER and user.id == author_id:
            return True
        if user.role == UserRole.ADMIN_ASSISTANT and bool(user.can_manage_house_info):
            return True
        return False

    def _validate_event_dates(self, payload: HouseEventCreate) -> None:
        if payload.ends_at and payload.ends_at < payload.starts_at:
            raise HTTPException(status_code=400, detail="End date cannot be earlier than start date")

    def get_events(self, user: User, house_id: int | None = None, active_only: bool = True):
        query = self.db.query(HouseEvent)
        if active_only:
            query = query.filter(HouseEvent.is_active.is_(True))

        if user.role == UserRole.RESIDENT and user.house_id:
            query = query.filter((HouseEvent.house_id == user.house_id) | (HouseEvent.house_id.is_(None)))
        elif house_id is not None:
            query = query.filter(HouseEvent.house_id == house_id)

        return query.order_by(HouseEvent.starts_at.asc(), HouseEvent.created_at.desc()).all()

    def create_event(self, user: User, payload: HouseEventCreate):
        self._ensure_write_access(user)
        self._validate_event_dates(payload)
        obj = HouseEvent(**payload.model_dump(), author_id=user.id)
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def update_event(self, user: User, event_id: int, payload: HouseEventCreate):
        self._ensure_write_access(user)
        self._validate_event_dates(payload)
        obj = self.db.query(HouseEvent).filter(HouseEvent.id == event_id).first()
        if not obj:
            raise HTTPException(status_code=404, detail="Event not found")
        if not self._can_manage(user, obj.author_id):
            raise HTTPException(status_code=403, detail="You can edit only your own records")

        data = payload.model_dump()
        for key, value in data.items():
            setattr(obj, key, value)

        self.db.commit()
        self.db.refresh(obj)
        return obj

    def delete_event(self, user: User, event_id: int):
        self._ensure_write_access(user)
        obj = self.db.query(HouseEvent).filter(HouseEvent.id == event_id).first()
        if not obj:
            raise HTTPException(status_code=404, detail="Event not found")
        if not self._can_manage(user, obj.author_id):
            raise HTTPException(status_code=403, detail="You can delete only your own records")
        self.db.delete(obj)
        self.db.commit()
        return {"status": "deleted"}

    def get_contacts(self, user: User, house_id: int | None = None, active_only: bool = True):
        query = self.db.query(EmergencyContact)
        if active_only:
            query = query.filter(EmergencyContact.is_active.is_(True))

        if user.role == UserRole.RESIDENT and user.house_id:
            query = query.filter((EmergencyContact.house_id == user.house_id) | (EmergencyContact.house_id.is_(None)))
        elif house_id is not None:
            query = query.filter(EmergencyContact.house_id == house_id)

        return query.order_by(EmergencyContact.sort_order.asc(), EmergencyContact.created_at.desc()).all()

    def create_contact(self, user: User, payload: EmergencyContactCreate):
        self._ensure_write_access(user)
        obj = EmergencyContact(**payload.model_dump(), author_id=user.id)
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def update_contact(self, user: User, contact_id: int, payload: EmergencyContactCreate):
        self._ensure_write_access(user)
        obj = self.db.query(EmergencyContact).filter(EmergencyContact.id == contact_id).first()
        if not obj:
            raise HTTPException(status_code=404, detail="Contact not found")
        if not self._can_manage(user, obj.author_id):
            raise HTTPException(status_code=403, detail="You can edit only your own records")

        data = payload.model_dump()
        for key, value in data.items():
            setattr(obj, key, value)

        self.db.commit()
        self.db.refresh(obj)
        return obj

    def delete_contact(self, user: User, contact_id: int):
        self._ensure_write_access(user)
        obj = self.db.query(EmergencyContact).filter(EmergencyContact.id == contact_id).first()
        if not obj:
            raise HTTPException(status_code=404, detail="Contact not found")
        if not self._can_manage(user, obj.author_id):
            raise HTTPException(status_code=403, detail="You can delete only your own records")
        self.db.delete(obj)
        self.db.commit()
        return {"status": "deleted"}

    def get_schedules(self, user: User, house_id: int | None = None, active_only: bool = True):
        query = self.db.query(HouseSchedule)
        if active_only:
            query = query.filter(HouseSchedule.is_active.is_(True))

        if user.role == UserRole.RESIDENT and user.house_id:
            query = query.filter((HouseSchedule.house_id == user.house_id) | (HouseSchedule.house_id.is_(None)))
        elif house_id is not None:
            query = query.filter(HouseSchedule.house_id == house_id)

        return query.order_by(HouseSchedule.created_at.desc()).all()

    def create_schedule(self, user: User, payload: HouseScheduleCreate):
        self._ensure_write_access(user)
        obj = HouseSchedule(**payload.model_dump(), author_id=user.id)
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def update_schedule(self, user: User, schedule_id: int, payload: HouseScheduleCreate):
        self._ensure_write_access(user)
        obj = self.db.query(HouseSchedule).filter(HouseSchedule.id == schedule_id).first()
        if not obj:
            raise HTTPException(status_code=404, detail="Schedule not found")
        if not self._can_manage(user, obj.author_id):
            raise HTTPException(status_code=403, detail="You can edit only your own records")

        data = payload.model_dump()
        for key, value in data.items():
            setattr(obj, key, value)

        self.db.commit()
        self.db.refresh(obj)
        return obj

    def delete_schedule(self, user: User, schedule_id: int):
        self._ensure_write_access(user)
        obj = self.db.query(HouseSchedule).filter(HouseSchedule.id == schedule_id).first()
        if not obj:
            raise HTTPException(status_code=404, detail="Schedule not found")
        if not self._can_manage(user, obj.author_id):
            raise HTTPException(status_code=403, detail="You can delete only your own records")
        self.db.delete(obj)
        self.db.commit()
        return {"status": "deleted"}
