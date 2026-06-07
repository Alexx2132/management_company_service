from datetime import date
from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.auth_validation import validate_login_value, validate_password_value
from app.core.profanity import ensure_clean_text
from app.core.security import get_password_hash
from app.models.executor import (
    ExecutorDayOff,
    ExecutorProfile,
    ExecutorSpecialty,
    ExecutorWorkSchedule,
    Specialty,
)
from app.models.remark import Remark, RemarkStatus
from app.models.ticket import Ticket, TicketStatus
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository
from app.schemas.executor import (
    ExecutorAvailabilityResponse,
    ExecutorCreateRequest,
    ExecutorDayOffCreate,
    ExecutorUpdateRequest,
    ExecutorWorkScheduleCreate,
    SpecialtyCreate,
)
from app.schemas.executor_recommendation import ExecutorRecommendationResponse
from app.services.executor_availability import get_executor_availability_state, moscow_today


class ExecutorService:
    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)

    @staticmethod
    def _normalize_optional(value: str | None) -> str:
        return (value or "").strip()

    def _display_name(self, profile: ExecutorProfile) -> str:
        user_name = self._normalize_optional(getattr(profile.user, "full_name", None))
        if user_name:
            return user_name

        profile_name = f"{profile.last_name or ''} {profile.first_name or ''}".strip()
        return profile_name or f"Исполнитель #{profile.user_id}"

    def _resolve_contact_phone(self, profile: ExecutorProfile) -> str | None:
        user = profile.user
        login_like_values = {
            self._normalize_optional(getattr(user, "login", None)).lower(),
        }
        login_like_values.discard("")

        direct_contact = self._normalize_optional(getattr(user, "contact_phone", None))
        if direct_contact and direct_contact.lower() not in login_like_values:
            return direct_contact

        legacy_profile_phone = self._normalize_optional(getattr(profile, "phone", None))
        if legacy_profile_phone and legacy_profile_phone.lower() not in login_like_values:
            return legacy_profile_phone

        return None

    def _attach_resolved_contact_phone(self, profile: ExecutorProfile) -> ExecutorProfile:
        if profile.user is not None:
            profile.user.contact_phone = self._resolve_contact_phone(profile)
        return profile

    def _primary_specialty_name(self, profile: ExecutorProfile) -> str | None:
        for spec in profile.specialties:
            if spec.is_primary and spec.specialty:
                return spec.specialty.name
        if profile.specialties:
            first = profile.specialties[0]
            return first.specialty.name if first.specialty else None
        return None

    def _profile_matches_ticket_category(self, profile: ExecutorProfile, ticket: Ticket) -> bool:
        category_name = self._normalize_optional(ticket.category.name if ticket.category else None).lower()
        if not category_name:
            return False

        aliases = {
            "plumber": ["сантех", "вод", "труб"],
            "electrician": ["электр", "свет"],
            "universal": ["разное", "прочее", "другое", "универс", "ремонт"],
        }

        for item in profile.specialties:
            specialty = item.specialty
            if not specialty:
                continue
            tokens = [
                self._normalize_optional(specialty.code).lower(),
                self._normalize_optional(specialty.name).lower(),
            ]
            for token in [value for value in tokens if value]:
                if token in category_name or category_name in token:
                    return True
                for alias in aliases.get(token, []):
                    if alias in category_name:
                        return True
        return False

    def _ticket_count(self, user_id: int, *statuses: TicketStatus) -> int:
        return (
            self.db.query(Ticket)
            .filter(Ticket.executor_id == user_id, Ticket.status.in_(list(statuses)))
            .count()
        )

    def list_specialties(self):
        return (
            self.db.query(Specialty)
            .options(joinedload(Specialty.executors))
            .order_by(Specialty.name.asc())
            .all()
        )

    def create_specialty(self, payload: SpecialtyCreate):
        ensure_clean_text(payload.name)
        name = payload.name.strip()
        code = payload.code.strip().lower()
        if not name or not code:
            raise HTTPException(status_code=400, detail="Specialty code and name are required")
        existing = (
            self.db.query(Specialty)
            .filter((Specialty.code == code) | (Specialty.name == name))
            .first()
        )
        if existing:
            raise HTTPException(status_code=409, detail="Specialty already exists")

        obj = Specialty(code=code, name=name)
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def delete_specialty(self, specialty_id: int) -> None:
        obj = (
            self.db.query(Specialty)
            .options(joinedload(Specialty.executors))
            .filter(Specialty.id == specialty_id)
            .first()
        )
        if not obj:
            raise HTTPException(status_code=404, detail="Специальность не найдена")
        if obj.executor_count > 0:
            raise HTTPException(
                status_code=400,
                detail="Нельзя удалить специальность, которая назначена хотя бы одному исполнителю",
            )

        self.db.delete(obj)
        self.db.commit()

    def _validate_specialties(self, specialty_ids: list[int], primary_specialty_id: int | None):
        specialties = []
        if specialty_ids:
            specialties = (
                self.db.query(Specialty)
                .filter(Specialty.id.in_(specialty_ids))
                .all()
            )

            found_ids = {item.id for item in specialties}
            missing = [sid for sid in specialty_ids if sid not in found_ids]
            if missing:
                raise HTTPException(status_code=404, detail=f"Specialties not found: {missing}")

        if primary_specialty_id is not None and primary_specialty_id not in specialty_ids:
            raise HTTPException(status_code=400, detail="Primary specialty must be included in specialty_ids")

        return specialties

    def list_executors(self, house_id: int | None = None, active_only: bool = False):
        query = (
            self.db.query(ExecutorProfile)
            .options(
                joinedload(ExecutorProfile.user),
                joinedload(ExecutorProfile.house),
                joinedload(ExecutorProfile.specialties).joinedload(ExecutorSpecialty.specialty),
                joinedload(ExecutorProfile.work_schedules),
                joinedload(ExecutorProfile.days_off),
            )
        )

        if house_id is not None:
            query = query.filter((ExecutorProfile.house_id == house_id) | (ExecutorProfile.house_id.is_(None)))

        if active_only:
            query = query.filter(ExecutorProfile.is_active.is_(True))

        profiles = query.order_by(ExecutorProfile.last_name.asc(), ExecutorProfile.first_name.asc()).all()
        return [self._attach_resolved_contact_phone(profile) for profile in profiles]

    def get_executor(self, executor_id: int):
        obj = (
            self.db.query(ExecutorProfile)
            .options(
                joinedload(ExecutorProfile.user),
                joinedload(ExecutorProfile.house),
                joinedload(ExecutorProfile.specialties).joinedload(ExecutorSpecialty.specialty),
                joinedload(ExecutorProfile.work_schedules),
                joinedload(ExecutorProfile.days_off),
            )
            .filter(ExecutorProfile.id == executor_id)
            .first()
        )
        if not obj:
            raise HTTPException(status_code=404, detail="Executor not found")
        return self._attach_resolved_contact_phone(obj)

    def get_executor_for_user(self, user: User):
        if user.role != UserRole.EXECUTOR:
            raise HTTPException(status_code=403, detail="Only executor can view own executor profile")

        obj = (
            self.db.query(ExecutorProfile)
            .options(
                joinedload(ExecutorProfile.user),
                joinedload(ExecutorProfile.house),
                joinedload(ExecutorProfile.specialties).joinedload(ExecutorSpecialty.specialty),
                joinedload(ExecutorProfile.work_schedules),
                joinedload(ExecutorProfile.days_off),
            )
            .filter(ExecutorProfile.user_id == user.id)
            .first()
        )
        if not obj:
            raise HTTPException(status_code=404, detail="Executor profile not found")
        return self._attach_resolved_contact_phone(obj)

    def _get_executor_for_user_record(self, user: User) -> ExecutorProfile:
        profile = (
            self.db.query(ExecutorProfile)
            .filter(ExecutorProfile.user_id == user.id)
            .first()
        )
        if not profile:
            raise HTTPException(status_code=404, detail="Executor profile not found")
        return profile

    def create_executor(self, payload: ExecutorCreateRequest):
        login = validate_login_value(payload.login)
        password = validate_password_value(payload.password)
        existing_login = self.user_repo.get_by_login_or_phone(login)
        if existing_login:
            raise HTTPException(status_code=409, detail="Логин занят")

        specialties = self._validate_specialties(payload.specialty_ids, payload.primary_specialty_id)
        ensure_clean_text(payload.notes)

        user = User(
            full_name=f"{payload.last_name} {payload.first_name}".strip(),
            phone=login,
            login=login,
            contact_phone=payload.phone,
            password_hash=get_password_hash(password),
            role=UserRole.EXECUTOR,
            specialty=None,
            house_id=payload.house_id,
            apartment_id=None,
            apartment=None,
        )
        self.db.add(user)
        self.db.flush()

        profile = ExecutorProfile(
            user_id=user.id,
            house_id=payload.house_id,
            first_name=payload.first_name,
            last_name=payload.last_name,
            middle_name=payload.middle_name,
            phone=payload.phone,
            notes=payload.notes,
            is_active=payload.is_active,
        )
        self.db.add(profile)
        self.db.flush()

        for item in specialties:
            self.db.add(
                ExecutorSpecialty(
                    executor_id=profile.id,
                    specialty_id=item.id,
                    is_primary=(payload.primary_specialty_id == item.id),
                )
            )

        self.db.commit()
        return self.get_executor(profile.id)

    def update_executor(self, executor_id: int, payload: ExecutorUpdateRequest):
        profile = self.get_executor(executor_id)
        data = payload.model_dump(exclude_unset=True)
        ensure_clean_text(data.get("notes"))

        specialty_ids = data.pop("specialty_ids", None)
        primary_specialty_id = data.pop("primary_specialty_id", None)

        for key, value in data.items():
            setattr(profile, key, value)

        if "phone" in data:
            profile.user.contact_phone = profile.phone
        if "house_id" in data:
            profile.user.house_id = profile.house_id
        if any(key in data for key in ["first_name", "last_name", "middle_name"]):
            profile.user.full_name = f"{profile.last_name or ''} {profile.first_name or ''}".strip()

        if specialty_ids is not None:
            specialties = self._validate_specialties(specialty_ids, primary_specialty_id)

            self.db.query(ExecutorSpecialty).filter(
                ExecutorSpecialty.executor_id == profile.id
            ).delete()

            for item in specialties:
                self.db.add(
                    ExecutorSpecialty(
                        executor_id=profile.id,
                        specialty_id=item.id,
                        is_primary=(primary_specialty_id == item.id),
                    )
                )

        self.db.commit()
        return self.get_executor(profile.id)

    def update_own_executor_profile(self, user: User, payload: ExecutorUpdateRequest):
        if user.role != UserRole.EXECUTOR:
            raise HTTPException(status_code=403, detail="Only executor can update own executor profile")

        profile = self._get_executor_for_user_record(user)
        data = payload.model_dump(exclude_unset=True)
        ensure_clean_text(data.get("notes"))

        for forbidden_key in ["house_id", "is_active", "specialty_ids", "primary_specialty_id"]:
            data.pop(forbidden_key, None)

        for key, value in data.items():
            setattr(profile, key, value)

        if "phone" in data:
            profile.user.contact_phone = profile.phone

        if any(key in data for key in ["first_name", "last_name", "middle_name"]):
            profile.user.full_name = f"{profile.last_name or ''} {profile.first_name or ''}".strip()

        self.db.commit()
        return self.get_executor(profile.id)

    def replace_work_schedules(self, executor_id: int, schedules: list[ExecutorWorkScheduleCreate]):
        profile = self.get_executor(executor_id)

        seen = set()
        for item in schedules:
            if item.weekday in seen:
                raise HTTPException(status_code=400, detail=f"Duplicate weekday in schedule: {item.weekday}")
            seen.add(item.weekday)

        self.db.query(ExecutorWorkSchedule).filter(
            ExecutorWorkSchedule.executor_id == profile.id
        ).delete()

        for item in schedules:
            self.db.add(
                ExecutorWorkSchedule(
                    executor_id=profile.id,
                    weekday=item.weekday,
                    work_start=item.work_start,
                    work_end=item.work_end,
                    is_active=item.is_active,
                )
            )

        self.db.commit()
        return self.get_executor(profile.id).work_schedules

    def replace_own_work_schedules(self, user: User, schedules: list[ExecutorWorkScheduleCreate]):
        raise HTTPException(status_code=403, detail="График исполнителя может изменять только администратор")

    def add_day_off(self, executor_id: int, payload: ExecutorDayOffCreate):
        profile = self.get_executor(executor_id)
        ensure_clean_text(payload.reason)

        existing = (
            self.db.query(ExecutorDayOff)
            .filter(
                ExecutorDayOff.executor_id == profile.id,
                ExecutorDayOff.off_date == payload.off_date
            )
            .first()
        )
        if existing:
            raise HTTPException(status_code=409, detail="Day off for this date already exists")

        obj = ExecutorDayOff(
            executor_id=profile.id,
            off_date=payload.off_date,
            reason=payload.reason,
            is_active=payload.is_active,
        )
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def add_own_day_off(self, user: User, payload: ExecutorDayOffCreate):
        if user.role != UserRole.EXECUTOR:
            raise HTTPException(status_code=403, detail="Only executor can manage own days off")
        profile = self._get_executor_for_user_record(user)
        return self.add_day_off(profile.id, payload)

    def list_day_offs(self, executor_id: int):
        profile = self.get_executor(executor_id)
        return (
            self.db.query(ExecutorDayOff)
            .filter(ExecutorDayOff.executor_id == profile.id)
            .order_by(ExecutorDayOff.off_date.asc())
            .all()
        )

    def delete_day_off(self, executor_id: int, day_off_id: int):
        profile = self.get_executor(executor_id)
        obj = (
            self.db.query(ExecutorDayOff)
            .filter(
                ExecutorDayOff.id == day_off_id,
                ExecutorDayOff.executor_id == profile.id,
            )
            .first()
        )
        if not obj:
            raise HTTPException(status_code=404, detail="Day off not found")
        self.db.delete(obj)
        self.db.commit()
        return {"status": "deleted"}

    def delete_own_day_off(self, user: User, day_off_id: int):
        if user.role != UserRole.EXECUTOR:
            raise HTTPException(status_code=403, detail="Only executor can manage own days off")
        profile = self._get_executor_for_user_record(user)
        return self.delete_day_off(profile.id, day_off_id)

    def list_availability(self, target_date: date, house_id: int | None = None):
        profiles = self.list_executors(house_id=house_id, active_only=True)

        result = []

        for profile in profiles:
            user_id = profile.user_id

            assigned_count = self.db.query(Ticket).filter(
                Ticket.executor_id == user_id,
                Ticket.status == TicketStatus.ASSIGNED
            ).count()

            in_progress_count = self.db.query(Ticket).filter(
                Ticket.executor_id == user_id,
                Ticket.status == TicketStatus.IN_PROGRESS
            ).count()

            active_total_count = self.db.query(Ticket).filter(
                Ticket.executor_id == user_id,
                Ticket.status.notin_([TicketStatus.DONE, TicketStatus.CLOSED, TicketStatus.CANCELED])
            ).count()

            availability = get_executor_availability_state(profile, target_date=target_date)

            primary_specialty = None
            for spec in profile.specialties:
                if spec.is_primary and spec.specialty:
                    primary_specialty = spec.specialty.name
                    break
            if primary_specialty is None and profile.specialties:
                first = profile.specialties[0]
                primary_specialty = first.specialty.name if first.specialty else None

            result.append(
                ExecutorAvailabilityResponse(
                    executor_id=profile.id,
                    user_id=profile.user_id,
                    full_name=self._display_name(profile),
                    contact_phone=self._resolve_contact_phone(profile),
                    house_id=profile.house_id,
                    primary_specialty=primary_specialty,
                    notes=profile.notes,
                    working_today=availability.is_working,
                    has_day_off_today=availability.has_day_off,
                    assigned_count=assigned_count,
                    in_progress_count=in_progress_count,
                    active_total_count=active_total_count,
                )
            )

        return result

    def recommend_for_ticket(self, ticket_id: int, top: int = 10) -> list[ExecutorRecommendationResponse]:
        ticket = self.db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        profiles = self.list_executors(house_id=ticket.house_id, active_only=True)
        today = moscow_today()
        result: list[ExecutorRecommendationResponse] = []

        for profile in profiles:
            assigned_count = self._ticket_count(profile.user_id, TicketStatus.ASSIGNED)
            in_progress_count = self._ticket_count(profile.user_id, TicketStatus.IN_PROGRESS)
            active_total_count = self._ticket_count(
                profile.user_id,
                TicketStatus.CREATED,
                TicketStatus.ASSIGNED,
                TicketStatus.IN_PROGRESS,
            )

            availability = get_executor_availability_state(profile, target_date=today)
            can_assign = availability.is_working and not availability.has_day_off
            matches_category = self._profile_matches_ticket_category(profile, ticket)

            score = 100
            reasons: list[str] = []

            if can_assign:
                score += 30
                reasons.append("Доступен сейчас")
            elif availability.has_day_off:
                score -= 60
                reasons.append("Сегодня отмечен выходной")
            else:
                score -= 35
                reasons.append("Сейчас вне рабочего графика")

            if matches_category:
                score += 25

            if profile.house_id is None:
                score += 5
                reasons.append("Может работать в любом доме")
            elif profile.house_id == ticket.house_id:
                score += 10
                reasons.append("Закреплён за этим домом")

            if assigned_count == 0 and in_progress_count == 0:
                score += 10
                reasons.append("Нет активной нагрузки")
            else:
                score -= assigned_count * 4 + in_progress_count * 7

            result.append(
                ExecutorRecommendationResponse(
                    executor_id=profile.id,
                    user_id=profile.user_id,
                    full_name=self._display_name(profile),
                    contact_phone=self._resolve_contact_phone(profile),
                    house_id=profile.house_id,
                    primary_specialty=self._primary_specialty_name(profile),
                    working_today=availability.is_working,
                    has_day_off_today=availability.has_day_off,
                    can_assign=can_assign,
                    assigned_count=assigned_count,
                    in_progress_count=in_progress_count,
                    active_total_count=active_total_count,
                    score=score,
                    reasons=reasons or ["Можно назначить по общей загрузке"],
                )
            )

        result.sort(
            key=lambda item: (
                0 if item.can_assign else 1,
                -item.score,
                item.active_total_count,
                item.full_name.lower(),
            )
        )
        return result[:max(1, top)]

    def get_executor_analytics(self, executor_id: int):
        profile = self.get_executor(executor_id)

        completed_tickets = (
            self.db.query(Ticket)
            .options(
                joinedload(Ticket.author),
                joinedload(Ticket.executor),
                joinedload(Ticket.house),
                joinedload(Ticket.apartment_ref),
                joinedload(Ticket.files),
            )
            .filter(
                Ticket.executor_id == profile.user_id,
                Ticket.status.in_([TicketStatus.DONE, TicketStatus.CLOSED]),
            )
            .order_by(Ticket.updated_at.desc())
            .limit(20)
            .all()
        )

        active_remarks = (
            self.db.query(Remark)
            .options(
                joinedload(Remark.issuer),
                joinedload(Remark.executor),
                joinedload(Remark.canceled_by),
            )
            .filter(
                Remark.executor_id == profile.user_id,
                Remark.status == RemarkStatus.ACTIVE,
            )
            .order_by(Remark.created_at.desc())
            .all()
        )

        archived_remarks = (
            self.db.query(Remark)
            .options(
                joinedload(Remark.issuer),
                joinedload(Remark.executor),
                joinedload(Remark.canceled_by),
            )
            .filter(
                Remark.executor_id == profile.user_id,
                Remark.status == RemarkStatus.CANCELED,
            )
            .order_by(Remark.created_at.desc())
            .all()
        )

        return {
            "profile": profile,
            "completed_tickets": completed_tickets,
            "active_remarks": active_remarks,
            "archived_remarks": archived_remarks,
        }
