import re

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.profanity import ensure_clean_text
from app.models.house_info import EmergencyContact, HouseEvent, HouseInfoType, HouseSchedule
from app.models.user import User, UserRole
from app.schemas.house_info import (
    EmergencyContactCreate,
    HouseEventCreate,
    HouseInfoTypeCreate,
    HouseScheduleCreate,
)
from app.services.notification_service import NotificationService
from app.services.permissions import can_manage_house_info, can_manage_service_settings, is_admin


class HouseInfoService:
    def __init__(self, db: Session):
        self.db = db

    def _ensure_write_access(self, user: User) -> None:
        if can_manage_house_info(user):
            return
        raise HTTPException(status_code=403, detail="Not enough permissions")

    def _ensure_type_manage_access(self, user: User) -> None:
        if can_manage_service_settings(user):
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

    def _normalize_type_code(self, code: str | None) -> str:
        normalized = re.sub(r"[^a-z0-9_]+", "_", (code or "").strip().lower())
        normalized = re.sub(r"_+", "_", normalized).strip("_")
        return normalized

    def _generate_type_code(self, type_group: str, name: str) -> str:
        base = self._normalize_type_code(name)
        if not base:
            base = f"{type_group}_type"

        code = base[:64]
        suffix = 2
        while (
            self.db.query(HouseInfoType)
            .filter(HouseInfoType.type_group == type_group, HouseInfoType.code == code)
            .first()
        ):
            suffix_text = f"_{suffix}"
            code = f"{base[:64 - len(suffix_text)]}{suffix_text}"
            suffix += 1
        return code

    def _ensure_type_exists(self, type_group: str, code: str) -> None:
        exists = (
            self.db.query(HouseInfoType)
            .filter(
                HouseInfoType.type_group == type_group,
                HouseInfoType.code == code,
                HouseInfoType.is_active.is_(True),
            )
            .first()
        )
        if not exists:
            raise HTTPException(status_code=400, detail="Unknown house info type")

    def _resident_ids_for_house_info(self, house_id: int | None) -> list[int]:
        query = self.db.query(User.id).filter(User.role == UserRole.RESIDENT)
        if house_id is not None:
            query = query.filter(User.house_id == house_id)
        return [row[0] for row in query.all()]

    def _notify_house_residents(
        self,
        house_id: int | None,
        title: str,
        message: str,
        notif_type: str,
    ) -> None:
        user_ids = self._resident_ids_for_house_info(house_id)
        if not user_ids:
            return
        NotificationService(self.db).notify_many(
            user_ids=user_ids,
            title=title,
            message=message,
            notif_type=notif_type,
            extra_data={"house_id": house_id},
        )

    def get_types(self, type_group: str | None = None, active_only: bool = True):
        query = self.db.query(HouseInfoType)
        if type_group is not None:
            query = query.filter(HouseInfoType.type_group == type_group)
        if active_only:
            query = query.filter(HouseInfoType.is_active.is_(True))
        return query.order_by(HouseInfoType.type_group.asc(), HouseInfoType.name.asc()).all()

    def create_type(self, user: User, payload: HouseInfoTypeCreate):
        self._ensure_type_manage_access(user)
        ensure_clean_text(payload.name)

        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Type name is required")

        code = self._normalize_type_code(payload.code) or self._generate_type_code(payload.type_group, name)
        existing = (
            self.db.query(HouseInfoType)
            .filter(
                HouseInfoType.type_group == payload.type_group,
                (HouseInfoType.code == code) | (HouseInfoType.name == name),
            )
            .first()
        )
        if existing:
            if not existing.is_active:
                existing.name = name
                existing.is_active = payload.is_active
                self.db.commit()
                self.db.refresh(existing)
                return existing
            raise HTTPException(status_code=409, detail="House info type already exists")

        obj = HouseInfoType(
            type_group=payload.type_group,
            code=code,
            name=name,
            is_active=payload.is_active,
        )
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        self._notify_house_residents(
            obj.house_id,
            title="Новая информация по дому",
            message=f"Добавлено событие: {obj.title}",
            notif_type="house_info_event",
        )
        return obj

    def delete_type(self, user: User, type_id: int):
        self._ensure_type_manage_access(user)
        obj = self.db.query(HouseInfoType).filter(HouseInfoType.id == type_id).first()
        if not obj:
            raise HTTPException(status_code=404, detail="House info type not found")
        obj.is_active = False
        self.db.commit()
        self.db.refresh(obj)
        return obj

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
        self._ensure_type_exists("event", payload.event_type)
        obj = HouseEvent(**payload.model_dump(), author_id=user.id)
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        self._notify_house_residents(
            obj.house_id,
            title="Новый полезный номер",
            message=f"Добавлен контакт: {obj.title}",
            notif_type="house_info_contact",
        )
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
        self._ensure_type_exists("event", data["event_type"])
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

        return query.order_by(EmergencyContact.created_at.asc()).all()

    def create_contact(self, user: User, payload: EmergencyContactCreate):
        self._ensure_write_access(user)
        obj = EmergencyContact(**payload.model_dump(), author_id=user.id)
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        self._notify_house_residents(
            obj.house_id,
            title="Новый график по дому",
            message=f"Добавлен график: {obj.title}",
            notif_type="house_info_schedule",
        )
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
        self._ensure_type_exists("schedule", payload.schedule_type)
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
        self._ensure_type_exists("schedule", data["schedule_type"])
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
