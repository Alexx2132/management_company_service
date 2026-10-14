from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.core.auth_validation import validate_contact_phone_value, validate_login_value, validate_password_value
from app.core.profanity import ensure_clean_text
from app.core.security import get_password_hash, generate_temporary_password, revoke_user_sessions
from app.models.app_settings import AppSettings
from app.models.location import Apartment, House
from app.models.password_recovery import PasswordRecoveryRequest
from app.models.user import User, UserChangeHistory, UserRole
from app.schemas.password_recovery import (
    PasswordRecoveryCreate,
    PasswordRecoveryDecision,
    PasswordRecoveryResetRequest,
)
from app.services.app_settings_service import AppSettingsService
from app.services.notification_service import NotificationService
from app.services.permissions import can_manage_password_recovery


class PasswordRecoveryService:
    STATUS_OPEN = "open"
    STATUS_RESET = "reset"
    STATUS_REJECTED = "rejected"
    VERIFIED_STATUSES = {"phone_match", "address_match", "phone_mismatch_address_match"}

    def __init__(self, db: Session):
        self.db = db

    def _ensure_can_manage(self, current_user: User) -> None:
        if not can_manage_password_recovery(current_user):
            raise HTTPException(status_code=403, detail="Недостаточно прав для восстановления доступа")

    def _settings(self) -> AppSettings:
        return AppSettingsService(self.db).get_settings()

    def _notify_managers(self, request_obj: PasswordRecoveryRequest) -> None:
        managers = (
            self.db.query(User)
            .filter(
                or_(
                    User.role == UserRole.ADMIN,
                    (User.role == UserRole.ADMIN_ASSISTANT) & (User.can_manage_password_recovery.is_(True)),
                )
            )
            .all()
        )
        if not managers:
            return

        NotificationService(self.db).notify_many(
            user_ids=[user.id for user in managers],
            title="Запрос на восстановление доступа",
            message=f"Пользователь {request_obj.requester_login} просит сбросить пароль.",
            notif_type="password_recovery_request",
            extra_data={"password_recovery_request_id": request_obj.id},
        )

    def list_house_options(self, query: str | None = None, limit: int = 50) -> list[House]:
        q = self.db.query(House)
        search = (query or "").strip()
        if search:
            like = f"%{search}%"
            q = q.filter(or_(House.city.ilike(like), House.address.ilike(like)))
        return q.order_by(House.address.asc()).limit(max(1, min(limit, 100))).all()

    def list_apartment_options(self, house_id: int) -> list[Apartment]:
        house = self.db.query(House).filter(House.id == house_id).first()
        if not house:
            raise HTTPException(status_code=404, detail="Дом не найден")
        return (
            self.db.query(Apartment)
            .filter(Apartment.house_id == house_id, Apartment.is_active.is_(True))
            .order_by(Apartment.entrance_id.asc(), Apartment.floor_number.asc(), Apartment.apartment_number.asc())
            .all()
        )

    def _resolve_location(self, payload: PasswordRecoveryCreate) -> tuple[int | None, int | None, str | None, str | None]:
        house_id = payload.house_id
        apartment_id = payload.apartment_id
        house_address = (payload.house_address or "").strip() or None
        apartment_number = (payload.apartment or "").strip() or None

        house = None
        if house_id:
            house = self.db.query(House).filter(House.id == house_id).first()
            if not house:
                raise HTTPException(status_code=400, detail="Выбранный дом не найден")
            house_address = ", ".join(part for part in [house.city, house.address] if part)

        if apartment_id:
            apartment = self.db.query(Apartment).filter(Apartment.id == apartment_id, Apartment.is_active.is_(True)).first()
            if not apartment:
                raise HTTPException(status_code=400, detail="Выбранная квартира не найдена")
            if house_id and apartment.house_id != house_id:
                raise HTTPException(status_code=400, detail="Квартира не относится к выбранному дому")
            house_id = apartment.house_id
            apartment_number = apartment.apartment_number
            if not house:
                house = self.db.query(House).filter(House.id == apartment.house_id).first()
                if house:
                    house_address = ", ".join(part for part in [house.city, house.address] if part)

        return house_id, apartment_id, house_address, apartment_number

    def create_request(self, payload: PasswordRecoveryCreate) -> PasswordRecoveryRequest:
        login = validate_login_value(payload.login)
        full_name = (payload.full_name or "").strip() or None
        contact_phone = payload.contact_phone.strip()
        house_id, apartment_id, house_address, apartment = self._resolve_location(payload)
        message = (payload.message or "").strip() or None

        contact_phone = validate_contact_phone_value(contact_phone, required=True)

        if apartment_id is not None:
            resident_exists = (
                self.db.query(User.id)
                .filter(
                    User.role == UserRole.RESIDENT,
                    or_(
                        User.apartment_id == apartment_id,
                        (User.house_id == house_id) & (User.apartment == str(apartment or "")),
                    ),
                )
                .first()
            )
            if resident_exists is None:
                raise HTTPException(
                    status_code=404,
                    detail="В выбранной квартире в сервисе пока нет зарегистрированных жителей",
                )

        ensure_clean_text(full_name or "", contact_phone, house_address or "", apartment or "", message or "")

        settings = self._settings()
        cooldown_minutes = max(1, int(getattr(settings, "password_recovery_cooldown_minutes", 5) or 5))
        last_request = (
            self.db.query(PasswordRecoveryRequest)
            .filter(PasswordRecoveryRequest.requester_login == login)
            .order_by(PasswordRecoveryRequest.created_at.desc())
            .first()
        )
        if last_request and last_request.created_at > datetime.utcnow() - timedelta(minutes=cooldown_minutes):
            raise HTTPException(
                status_code=429,
                detail=f"Повторный запрос можно отправить через {cooldown_minutes} минут.",
            )

        matched_user = (
            self.db.query(User)
            .filter(or_(User.login == login, User.phone == login))
            .first()
        )

        request_obj = PasswordRecoveryRequest(
            requester_login=login,
            requester_name=full_name,
            contact_phone=contact_phone,
            house_id=house_id,
            apartment_id=apartment_id,
            house_address=house_address,
            apartment=apartment,
            message=message,
            status=self.STATUS_OPEN,
            matched_user_id=matched_user.id if matched_user else None,
        )
        self.db.add(request_obj)
        self.db.commit()
        self.db.refresh(request_obj)
        self._notify_managers(request_obj)
        return request_obj

    def list_requests(self, current_user: User, status: str | None = None, skip: int = 0, limit: int = 100) -> list[PasswordRecoveryRequest]:
        self._ensure_can_manage(current_user)
        q = (
            self.db.query(PasswordRecoveryRequest)
            .options(
                joinedload(PasswordRecoveryRequest.matched_user).joinedload(User.house),
                joinedload(PasswordRecoveryRequest.matched_user).joinedload(User.apartment_ref),
                joinedload(PasswordRecoveryRequest.processed_by),
                joinedload(PasswordRecoveryRequest.house),
                joinedload(PasswordRecoveryRequest.apartment_ref),
            )
        )
        if status:
            q = q.filter(PasswordRecoveryRequest.status == status)
        return q.order_by(PasswordRecoveryRequest.created_at.desc()).offset(skip).limit(limit).all()

    def get_request(self, request_id: int, current_user: User) -> PasswordRecoveryRequest:
        self._ensure_can_manage(current_user)
        request_obj = (
            self.db.query(PasswordRecoveryRequest)
            .options(
                joinedload(PasswordRecoveryRequest.matched_user).joinedload(User.house),
                joinedload(PasswordRecoveryRequest.matched_user).joinedload(User.apartment_ref),
                joinedload(PasswordRecoveryRequest.processed_by),
                joinedload(PasswordRecoveryRequest.house),
                joinedload(PasswordRecoveryRequest.apartment_ref),
            )
            .filter(PasswordRecoveryRequest.id == request_id)
            .first()
        )
        if not request_obj:
            raise HTTPException(status_code=404, detail="Password recovery request not found")
        return request_obj

    def reset_password(self, request_id: int, payload: PasswordRecoveryResetRequest, current_user: User) -> tuple[PasswordRecoveryRequest, str]:
        request_obj = self.get_request(request_id, current_user)
        if request_obj.status != self.STATUS_OPEN:
            raise HTTPException(status_code=400, detail="Request is already processed")
        if not request_obj.matched_user:
            raise HTTPException(status_code=400, detail="User for this request was not found")
        if current_user.role != UserRole.ADMIN and request_obj.matched_user.role != UserRole.RESIDENT:
            raise HTTPException(status_code=403, detail="Помощник может восстанавливать доступ только жителям")
        if request_obj.verification_status not in self.VERIFIED_STATUSES:
            raise HTTPException(status_code=400, detail=request_obj.verification_note)

        temporary_password = validate_password_value((payload.temporary_password or "").strip() or generate_temporary_password())
        request_obj.matched_user.password_hash = get_password_hash(temporary_password)
        request_obj.matched_user.must_change_password = True
        revoke_user_sessions(self.db, request_obj.matched_user)
        request_obj.status = self.STATUS_RESET
        request_obj.processed_by_id = current_user.id
        request_obj.processed_at = datetime.utcnow()
        request_obj.admin_comment = (payload.admin_comment or "").strip() or None
        self.db.add(UserChangeHistory(
            user_id=request_obj.matched_user.id,
            actor_id=current_user.id,
            field_name="password_reset",
            old_value=None,
            new_value="temporary_password",
        ))
        self.db.commit()
        self.db.refresh(request_obj)
        NotificationService(self.db).notify_user(
            user_id=request_obj.matched_user.id,
            title="Пароль сброшен",
            message="Администратор установил временный пароль. После входа замените его на новый.",
            notif_type="password_reset",
            extra_data={"password_recovery_request_id": request_obj.id},
        )
        return request_obj, temporary_password

    def reject_request(self, request_id: int, payload: PasswordRecoveryDecision, current_user: User) -> PasswordRecoveryRequest:
        request_obj = self.get_request(request_id, current_user)
        if request_obj.status != self.STATUS_OPEN:
            raise HTTPException(status_code=400, detail="Request is already processed")

        request_obj.status = self.STATUS_REJECTED
        request_obj.processed_by_id = current_user.id
        request_obj.processed_at = datetime.utcnow()
        request_obj.admin_comment = (payload.admin_comment or "").strip() or None
        self.db.commit()
        self.db.refresh(request_obj)
        return request_obj
