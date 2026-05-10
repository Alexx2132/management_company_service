from datetime import timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.security import get_password_hash, verify_password
from app.models.location import Apartment
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserAdminUpdate, UserBan, UserCreate, UserUpdate


class UserService:
    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)

    def _normalize_banned_until(self, value):
        if value is None:
            return None

        if value.tzinfo is None:
            value = value.replace(tzinfo=ZoneInfo("Europe/Moscow"))

        return value.astimezone(timezone.utc).replace(tzinfo=None, microsecond=0)

    def _apply_apartment_binding(self, payload: dict) -> dict:
        apartment_id = payload.get("apartment_id")

        if apartment_id is None:
            return payload

        apartment_obj = (
            self.db.query(Apartment)
            .filter(Apartment.id == apartment_id, Apartment.is_active.is_(True))
            .first()
        )
        if not apartment_obj:
            raise HTTPException(status_code=404, detail="Apartment not found")

        requested_house_id = payload.get("house_id")
        if requested_house_id is not None and requested_house_id != apartment_obj.house_id:
            raise HTTPException(
                status_code=400,
                detail="Apartment does not belong to selected house"
            )

        payload["house_id"] = apartment_obj.house_id

        if not payload.get("apartment"):
            payload["apartment"] = apartment_obj.apartment_number

        return payload

    def _normalize_auth_fields(self, payload: dict) -> dict:
        login = payload.get("login")
        phone = payload.get("phone")

        # Для обратной совместимости: если логин не передан, используем старое поле phone.
        if not login and phone:
            payload["login"] = phone

        if not payload.get("login"):
            raise HTTPException(status_code=400, detail="Login is required")

        # В проекте legacy-поле phone продолжает хранить логин для совместимости.
        payload["phone"] = payload["login"]

        return payload

    def _normalize_dispatcher_permissions(self, payload: dict, current_role: UserRole | None = None) -> dict:
        role = payload.get("role", current_role)

        if role == UserRole.DISPATCHER or str(role).lower() == UserRole.DISPATCHER.value:
            payload["can_manage_houses"] = bool(payload.get("can_manage_houses", False))
            payload["can_ban_residents"] = bool(payload.get("can_ban_residents", False))
            return payload

        if "can_manage_houses" in payload:
            payload["can_manage_houses"] = False
        if "can_ban_residents" in payload:
            payload["can_ban_residents"] = False
        return payload

    def _can_ban_residents(self, actor: User) -> bool:
        if actor.role == UserRole.ADMIN:
            return True
        return actor.role == UserRole.DISPATCHER and bool(actor.can_ban_residents)

    def create_user(self, user_in: UserCreate) -> User:
        user_data = user_in.model_dump()

        user_data = self._normalize_auth_fields(user_data)
        user_data = self._normalize_dispatcher_permissions(user_data)

        existing_by_login = self.user_repo.get_by_login(user_data["login"])
        if existing_by_login:
            raise HTTPException(status_code=409, detail="User with this login already exists")

        if user_data.get("phone"):
            existing_by_phone = self.user_repo.get_by_phone(user_data["phone"])
            if existing_by_phone:
                raise HTTPException(status_code=409, detail="User with this phone already exists")

        plain_password = user_data.pop("password")
        user_data["password_hash"] = get_password_hash(plain_password)

        user_data = self._apply_apartment_binding(user_data)

        return self.user_repo.create(user_data)

    def authenticate(self, username: str, password: str) -> User | None:
        user = self.user_repo.get_by_login(username)
        if not user:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user

    def change_password(self, user_id: int, old_password: str, new_password: str):
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if not verify_password(old_password, user.password_hash):
            raise HTTPException(status_code=400, detail="Incorrect old password")

        user.password_hash = get_password_hash(new_password)
        self.user_repo.db.commit()
        return {"status": "password updated"}

    def ban_user(self, user_id: int, ban_data: UserBan, admin_user: User):
        if not self._can_ban_residents(admin_user):
            raise HTTPException(status_code=403, detail="Not enough permissions to manage resident bans")

        user_to_ban = self.user_repo.get_by_id(user_id)
        if not user_to_ban:
            raise HTTPException(404, "User not found")

        if user_to_ban.role != UserRole.RESIDENT:
            raise HTTPException(status_code=400, detail="Only residents can be banned")

        banned_until = self._normalize_banned_until(ban_data.banned_until)
        user_to_ban.banned_until = banned_until
        self.user_repo.db.commit()

        status = "banned" if banned_until else "unbanned"
        return {"status": status, "until": banned_until}

    def update_user(self, user_id: int, update_data: UserUpdate) -> User:
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(404, "User not found")

        data = update_data.model_dump(exclude_unset=True)
        data = self._normalize_auth_fields(data) if ("login" in data or "phone" in data) else data

        if "login" in data and data["login"]:
            existing_login = self.user_repo.get_by_login(data["login"])
            if existing_login and existing_login.id != user_id:
                raise HTTPException(status_code=400, detail="Login already exists")

        if "phone" in data and data["phone"]:
            existing_phone = self.user_repo.get_by_phone(data["phone"])
            if existing_phone and existing_phone.id != user_id:
                raise HTTPException(status_code=400, detail="Phone number already exists")

        for key, value in data.items():
            setattr(user, key, value)

        self.user_repo.db.commit()
        self.user_repo.db.refresh(user)
        return user

    def admin_update_user(self, user_id: int, update_data: UserAdminUpdate, admin_user: User) -> User:
        if admin_user.role != UserRole.ADMIN:
            raise HTTPException(status_code=403, detail="Only admin can update arbitrary users")

        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        data = update_data.model_dump(exclude_unset=True)
        data = self._normalize_auth_fields(data) if ("login" in data or "phone" in data) else data

        if "login" in data and data["login"]:
            existing_login = self.user_repo.get_by_login(data["login"])
            if existing_login and existing_login.id != user_id:
                raise HTTPException(status_code=400, detail="Login already exists")

        if "phone" in data and data["phone"]:
            existing_phone = self.user_repo.get_by_phone(data["phone"])
            if existing_phone and existing_phone.id != user_id:
                raise HTTPException(status_code=400, detail="Phone number already exists")

        data = self._apply_apartment_binding(data)
        data = self._normalize_dispatcher_permissions(data, current_role=user.role)

        for key, value in data.items():
            setattr(user, key, value)

        self.db.commit()
        self.db.refresh(user)
        return user
