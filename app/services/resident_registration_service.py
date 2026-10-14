from datetime import datetime
import secrets
import string

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.core.auth_validation import validate_contact_phone_value, validate_login_value, validate_password_value
from app.core.profanity import ensure_clean_text
from app.core.security import get_password_hash, generate_temporary_password
from app.models.location import Apartment, House
from app.models.resident_registration import ResidentRegistrationRequest
from app.models.user import User, UserRole
from app.schemas.resident_registration import (
    ResidentRegistrationApproveRequest,
    ResidentRegistrationCreate,
    ResidentRegistrationDecision,
)
from app.services.notification_service import NotificationService
from app.services.permissions import can_approve_registrations


class ResidentRegistrationService:
    STATUS_OPEN = "open"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"

    def __init__(self, db: Session):
        self.db = db

    def _ensure_can_manage(self, current_user: User) -> None:
        if not can_approve_registrations(current_user):
            raise HTTPException(status_code=403, detail="Недостаточно прав для подтверждения регистраций")

    def _generate_temporary_password(self) -> str:
        alphabet = string.ascii_letters + string.digits
        while True:
            password = "".join(secrets.choice(alphabet) for _ in range(10))
            if any(ch.islower() for ch in password) and any(ch.isupper() for ch in password) and any(ch.isdigit() for ch in password):
                return password

    def _ensure_login_available(self, login: str, current_request_id: int | None = None) -> None:
        existing_user = self.db.query(User.id).filter(or_(User.login == login, User.phone == login)).first()
        if existing_user:
            raise HTTPException(status_code=409, detail="Логин занят")
        q = (
            self.db.query(ResidentRegistrationRequest.id)
            .filter(
                ResidentRegistrationRequest.login == login,
                ResidentRegistrationRequest.status == self.STATUS_OPEN,
            )
        )
        if current_request_id is not None:
            q = q.filter(ResidentRegistrationRequest.id != current_request_id)
        existing_request = q.first()
        if existing_request:
            raise HTTPException(status_code=409, detail="Заявка с таким логином уже ожидает рассмотрения")

    def _resolve_location(self, house_id: int, apartment_id: int) -> tuple[House, Apartment]:
        house = self.db.query(House).filter(House.id == house_id).first()
        if not house:
            raise HTTPException(status_code=400, detail="Выбранный дом не найден")

        apartment = self.db.query(Apartment).filter(Apartment.id == apartment_id, Apartment.is_active.is_(True)).first()
        if not apartment:
            raise HTTPException(status_code=400, detail="Выбранная квартира не найдена")
        if apartment.house_id != house.id:
            raise HTTPException(status_code=400, detail="Квартира не относится к выбранному дому")

        return house, apartment

    def _ensure_apartment_accepts_resident(self, apartment_id: int) -> None:
        blocked = (
            self.db.query(User.id)
            .filter(
                User.role == UserRole.RESIDENT,
                User.apartment_id == apartment_id,
                User.blocks_apartment_resident_additions.is_(True),
            )
            .first()
        )
        if blocked:
            raise HTTPException(
                status_code=409,
                detail="Добавление жителей в эту квартиру запрещено зарегистрированным жителем",
            )

    def _notify_managers(self, request_obj: ResidentRegistrationRequest) -> None:
        managers = (
            self.db.query(User)
            .filter(
                or_(
                    User.role == UserRole.ADMIN,
                    (User.role == UserRole.ADMIN_ASSISTANT) & (User.can_approve_registrations.is_(True)),
                )
            )
            .all()
        )
        if not managers:
            return

        NotificationService(self.db).notify_many(
            user_ids=[user.id for user in managers],
            title="Новая заявка на регистрацию",
            message=f"{request_obj.full_name} просит создать учетную запись жителя.",
            notif_type="registration_request",
            extra_data={"registration_request_id": request_obj.id},
        )

    def list_house_options(self, query: str | None = None, limit: int = 50) -> list[House]:
        q = self.db.query(House)
        search = (query or "").strip()
        if search:
            like = f"%{search}%"
            q = q.filter(or_(House.city.ilike(like), House.address.ilike(like)))
        return q.order_by(House.address.asc()).limit(max(1, min(limit, 100))).all()

    def list_apartment_options(self, house_id: int) -> list[Apartment]:
        house = self.db.query(House.id).filter(House.id == house_id).first()
        if not house:
            raise HTTPException(status_code=404, detail="Дом не найден")
        return (
            self.db.query(Apartment)
            .filter(Apartment.house_id == house_id, Apartment.is_active.is_(True))
            .order_by(Apartment.entrance_id.asc(), Apartment.floor_number.asc(), Apartment.apartment_number.asc())
            .all()
        )

    def create_request(self, payload: ResidentRegistrationCreate) -> ResidentRegistrationRequest:
        login = validate_login_value(payload.login)
        full_name = payload.full_name.strip()
        contact_phone = payload.contact_phone.strip()
        message = (payload.message or "").strip() or None

        if not full_name:
            raise HTTPException(status_code=400, detail="Введите имя")
        contact_phone = validate_contact_phone_value(contact_phone, required=True)

        ensure_clean_text(login, full_name, contact_phone, message or "")
        self._ensure_login_available(login)
        house, apartment = self._resolve_location(payload.house_id, payload.apartment_id)
        self._ensure_apartment_accepts_resident(apartment.id)

        request_obj = ResidentRegistrationRequest(
            login=login,
            full_name=full_name,
            contact_phone=contact_phone,
            house_id=house.id,
            apartment_id=apartment.id,
            house_address=", ".join(part for part in [house.city, house.address] if part),
            apartment=apartment.apartment_number,
            message=message,
            status=self.STATUS_OPEN,
        )
        self.db.add(request_obj)
        self.db.commit()
        self.db.refresh(request_obj)
        self._notify_managers(request_obj)
        return request_obj

    def list_requests(self, current_user: User, status: str | None = None, skip: int = 0, limit: int = 100) -> list[ResidentRegistrationRequest]:
        self._ensure_can_manage(current_user)
        q = self.db.query(ResidentRegistrationRequest).options(
            joinedload(ResidentRegistrationRequest.house),
            joinedload(ResidentRegistrationRequest.apartment_ref),
            joinedload(ResidentRegistrationRequest.created_user),
            joinedload(ResidentRegistrationRequest.processed_by),
        )
        if status:
            q = q.filter(ResidentRegistrationRequest.status == status)
        return q.order_by(ResidentRegistrationRequest.created_at.desc()).offset(skip).limit(limit).all()

    def get_request(self, request_id: int, current_user: User) -> ResidentRegistrationRequest:
        self._ensure_can_manage(current_user)
        request_obj = (
            self.db.query(ResidentRegistrationRequest)
            .options(
                joinedload(ResidentRegistrationRequest.house),
                joinedload(ResidentRegistrationRequest.apartment_ref),
                joinedload(ResidentRegistrationRequest.created_user),
                joinedload(ResidentRegistrationRequest.processed_by),
            )
            .filter(ResidentRegistrationRequest.id == request_id)
            .first()
        )
        if not request_obj:
            raise HTTPException(status_code=404, detail="Заявка на регистрацию не найдена")
        return request_obj

    def approve_request(self, request_id: int, payload: ResidentRegistrationApproveRequest, current_user: User) -> tuple[ResidentRegistrationRequest, User, str]:
        request_obj = self.get_request(request_id, current_user)
        if request_obj.status != self.STATUS_OPEN:
            raise HTTPException(status_code=400, detail="Заявка уже обработана")

        self._ensure_login_available(request_obj.login, current_request_id=request_obj.id)
        _, apartment = self._resolve_location(request_obj.house_id, request_obj.apartment_id)
        self._ensure_apartment_accepts_resident(apartment.id)

        temporary_password = validate_password_value((payload.temporary_password or "").strip() or generate_temporary_password())
        user = User(
            full_name=request_obj.full_name,
            login=request_obj.login,
            phone=request_obj.login,
            contact_phone=request_obj.contact_phone,
            password_hash=get_password_hash(temporary_password),
            role=UserRole.RESIDENT,
            house_id=request_obj.house_id,
            apartment_id=request_obj.apartment_id,
            apartment=request_obj.apartment,
            must_change_password=True,
        )
        self.db.add(user)
        self.db.flush()

        request_obj.status = self.STATUS_APPROVED
        request_obj.created_user_id = user.id
        request_obj.processed_by_id = current_user.id
        request_obj.processed_at = datetime.utcnow()
        request_obj.admin_comment = (payload.admin_comment or "").strip() or None
        self.db.commit()
        self.db.refresh(user)
        self.db.refresh(request_obj)
        return request_obj, user, temporary_password

    def reject_request(self, request_id: int, payload: ResidentRegistrationDecision, current_user: User) -> ResidentRegistrationRequest:
        request_obj = self.get_request(request_id, current_user)
        if request_obj.status != self.STATUS_OPEN:
            raise HTTPException(status_code=400, detail="Заявка уже обработана")

        request_obj.status = self.STATUS_REJECTED
        request_obj.processed_by_id = current_user.id
        request_obj.processed_at = datetime.utcnow()
        request_obj.admin_comment = (payload.admin_comment or "").strip() or None
        self.db.commit()
        self.db.refresh(request_obj)
        return request_obj
