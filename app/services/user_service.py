from datetime import timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.auth_validation import normalize_allowed_priorities, validate_login_value, validate_password_value
from app.core.security import get_password_hash, verify_password
from app.models.executor import ExecutorProfile
from app.models.location import Apartment
from app.models.user import User, UserChangeHistory, UserRole
from app.repositories.user_repository import UserRepository
from app.schemas.user import ResidentAutofillRequest, UserAdminUpdate, UserBan, UserCreate, UserUpdate
from app.services.notification_service import NotificationService
from app.services.permissions import can_ban_residents, can_create_users, is_admin, is_admin_assistant


class UserService:
    ASSISTANT_PERMISSION_FIELDS = [
        "can_manage_houses",
        "can_ban_residents",
        "can_create_users",
        "can_manage_executor_schedules",
        "can_manage_service_settings",
        "can_manage_remarks",
        "can_manage_house_info",
        "can_manage_announcements",
    ]
    DISPATCHER_PERMISSION_FIELDS = ["can_manage_houses", "can_ban_residents"]

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
            payload["login"] = validate_login_value(phone)
        elif login:
            payload["login"] = validate_login_value(login)

        if not payload.get("login"):
            raise HTTPException(status_code=400, detail="Введите логин")

        # В проекте legacy-поле phone продолжает хранить логин для совместимости.
        payload["phone"] = payload["login"]

        return payload

    def _ensure_login_available(self, login: str, current_user_id: int | None = None) -> None:
        existing_user = self.user_repo.get_by_login_or_phone(login)
        if existing_user and existing_user.id != current_user_id:
            raise HTTPException(status_code=409, detail="Логин занят")

    def _record_profile_changes(self, user: User, data: dict, actor: User | None = None) -> None:
        tracked_fields = {
            "login": "login",
            "full_name": "full_name",
            "contact_phone": "contact_phone",
        }
        for data_key, field_name in tracked_fields.items():
            if data_key not in data:
                continue
            old_value = getattr(user, data_key, None)
            new_value = data.get(data_key)
            old_text = "" if old_value is None else str(old_value)
            new_text = "" if new_value is None else str(new_value)
            if old_text == new_text:
                continue
            self.db.add(UserChangeHistory(
                user_id=user.id,
                actor_id=actor.id if actor else user.id,
                field_name=field_name,
                old_value=old_text or None,
                new_value=new_text or None,
            ))

    def _sync_executor_profile_name(self, user: User, full_name: str | None) -> None:
        if user.role != UserRole.EXECUTOR or not full_name:
            return

        profile = self.db.query(ExecutorProfile).filter(ExecutorProfile.user_id == user.id).first()
        if not profile:
            return

        parts = full_name.strip().split()
        if not parts:
            return

        if len(parts) == 1:
            profile.last_name = ""
            profile.first_name = parts[0]
            profile.middle_name = None
            return

        profile.last_name = parts[0]
        profile.first_name = parts[1]
        profile.middle_name = " ".join(parts[2:]) if len(parts) > 2 else None

    def _role_value(self, role: UserRole | str | None) -> str | None:
        if role is None:
            return None
        return role.value if isinstance(role, UserRole) else str(role).lower()

    def _normalize_role_permissions(self, payload: dict, current_role: UserRole | None = None) -> dict:
        role = payload.get("role", current_role)
        role_value = self._role_value(role)
        permission_fields_present = any(key in payload for key in self.ASSISTANT_PERMISSION_FIELDS)
        priorities_present = "allowed_ticket_priorities" in payload
        if current_role is not None and "role" not in payload and not permission_fields_present and not priorities_present:
            return payload

        if role_value == UserRole.ADMIN_ASSISTANT.value:
            for key in self.ASSISTANT_PERMISSION_FIELDS:
                payload[key] = bool(payload.get(key, False))
            payload["allowed_ticket_priorities"] = None
            return payload

        if role_value == UserRole.DISPATCHER.value:
            for key in self.DISPATCHER_PERMISSION_FIELDS:
                payload[key] = bool(payload.get(key, False))
            for key in self.ASSISTANT_PERMISSION_FIELDS:
                if key not in self.DISPATCHER_PERMISSION_FIELDS:
                    payload[key] = False
            if priorities_present or "role" in payload:
                payload["allowed_ticket_priorities"] = normalize_allowed_priorities(payload.get("allowed_ticket_priorities"))
            return payload

        for key in self.ASSISTANT_PERMISSION_FIELDS:
            payload[key] = False
        payload["allowed_ticket_priorities"] = None
        return payload

    def _ensure_can_create_target_role(self, actor: User | None, target_role: UserRole) -> None:
        if target_role == UserRole.ADMIN:
            existing_admin = self.db.query(User.id).filter(User.role == UserRole.ADMIN).first()
            if existing_admin is None and actor is None:
                return
            raise HTTPException(
                status_code=400,
                detail="Нельзя создать второго администратора. Создайте пользователя с ролью помощника администратора.",
            )

        if actor is None:
            return

        if not can_create_users(actor):
            raise HTTPException(status_code=403, detail="Not enough permissions to create users")

        if is_admin_assistant(actor) and target_role == UserRole.ADMIN_ASSISTANT:
            raise HTTPException(status_code=403, detail="Only admin can create admin assistants")

    def _validate_admin_update_role_change(self, actor: User, target_user: User, data: dict) -> None:
        if is_admin(actor):
            if data.get("role") == UserRole.ADMIN:
                raise HTTPException(
                    status_code=400,
                    detail="Нельзя назначить второго администратора. Используйте роль помощника администратора.",
                )
            return

        if not can_create_users(actor):
            raise HTTPException(status_code=403, detail="Not enough permissions to update users")

        if target_user.role in [UserRole.ADMIN, UserRole.ADMIN_ASSISTANT]:
            raise HTTPException(status_code=403, detail="Only admin can update admin or assistant accounts")

        if data.get("role") in [UserRole.ADMIN, UserRole.ADMIN_ASSISTANT]:
            raise HTTPException(status_code=403, detail="Only admin can assign admin assistant role")

        for key in self.ASSISTANT_PERMISSION_FIELDS:
            data.pop(key, None)

    def create_user(self, user_in: UserCreate, actor: User | None = None) -> User:
        user_data = user_in.model_dump()

        user_data = self._normalize_auth_fields(user_data)
        target_role = user_data.get("role", UserRole.RESIDENT)
        self._ensure_can_create_target_role(actor, target_role)
        user_data = self._normalize_role_permissions(user_data)

        self._ensure_login_available(user_data["login"])

        plain_password = validate_password_value(user_data.pop("password"))
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

        user.password_hash = get_password_hash(validate_password_value(new_password))
        self.user_repo.db.commit()
        return {"status": "password updated"}

    def ban_user(self, user_id: int, ban_data: UserBan, admin_user: User):
        if not can_ban_residents(admin_user):
            raise HTTPException(status_code=403, detail="Not enough permissions to manage resident bans")

        user_to_ban = self.user_repo.get_by_id(user_id)
        if not user_to_ban:
            raise HTTPException(404, "User not found")

        if user_to_ban.role != UserRole.RESIDENT:
            raise HTTPException(status_code=400, detail="Only residents can be banned")

        was_banned = user_to_ban.banned_until is not None
        banned_until = self._normalize_banned_until(ban_data.banned_until)
        user_to_ban.banned_until = banned_until
        user_to_ban.ban_reason = ban_data.ban_reason.strip() if banned_until and ban_data.ban_reason else None
        self.user_repo.db.commit()

        status = "banned" if banned_until else "unbanned"
        if not banned_until and was_banned:
            NotificationService(self.db).notify_user(
                user_id=user_to_ban.id,
                title="Блокировка снята",
                message="Вы можете снова отправлять заявки.",
                notif_type="ban_lifted",
            )
        return {"status": status, "until": banned_until, "reason": user_to_ban.ban_reason}

    def update_user(self, user_id: int, update_data: UserUpdate, actor: User | None = None) -> User:
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(404, "User not found")

        data = update_data.model_dump(exclude_unset=True)
        data = self._normalize_auth_fields(data) if ("login" in data or "phone" in data) else data

        if "login" in data and data["login"]:
            self._ensure_login_available(data["login"], current_user_id=user_id)

        self._record_profile_changes(user, data, actor)

        for key, value in data.items():
            setattr(user, key, value)

        if "full_name" in data:
            self._sync_executor_profile_name(user, data.get("full_name"))

        self.user_repo.db.commit()
        self.user_repo.db.refresh(user)
        return user

    def admin_update_user(self, user_id: int, update_data: UserAdminUpdate, admin_user: User) -> User:
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        data = update_data.model_dump(exclude_unset=True)
        self._validate_admin_update_role_change(admin_user, user, data)
        data = self._normalize_auth_fields(data) if ("login" in data or "phone" in data) else data

        if "login" in data and data["login"]:
            self._ensure_login_available(data["login"], current_user_id=user_id)

        data = self._apply_apartment_binding(data)
        data = self._normalize_role_permissions(data, current_role=user.role)

        self._record_profile_changes(user, data, admin_user)

        for key, value in data.items():
            setattr(user, key, value)

        if "full_name" in data:
            self._sync_executor_profile_name(user, data.get("full_name"))

        self.db.commit()
        self.db.refresh(user)
        return user

    def autofill_residents(self, payload: ResidentAutofillRequest, actor: User) -> dict:
        if not can_create_users(actor):
            raise HTTPException(status_code=403, detail="Not enough permissions to create users")

        apartments = (
            self.db.query(Apartment)
            .options(joinedload(Apartment.entrance))
            .filter(Apartment.house_id == payload.house_id, Apartment.is_active.is_(True))
            .order_by(Apartment.entrance_id.asc(), Apartment.floor_number.asc(), Apartment.apartment_number.asc())
            .all()
        )
        if not apartments:
            raise HTTPException(status_code=404, detail="В выбранном доме нет квартир для автозаполнения")

        apartment_ids = [item.id for item in apartments]
        occupied_apartment_ids = {
            row[0]
            for row in (
                self.db.query(User.apartment_id)
                .filter(
                    User.role == UserRole.RESIDENT,
                    User.apartment_id.in_(apartment_ids),
                )
                .all()
            )
            if row[0] is not None
        }
        occupied_apartment_numbers = {
            str(row[0])
            for row in (
                self.db.query(User.apartment)
                .filter(
                    User.role == UserRole.RESIDENT,
                    User.house_id == payload.house_id,
                    User.apartment.isnot(None),
                )
                .all()
            )
            if row[0] is not None
        }

        target_apartments = [
            item
            for item in apartments
            if item.id not in occupied_apartment_ids and str(item.apartment_number) not in occupied_apartment_numbers
        ]
        skipped_occupied_count = len(apartments) - len(target_apartments)
        if not target_apartments:
            return {
                "created_count": 0,
                "skipped_occupied_count": skipped_occupied_count,
                "created_logins": [],
            }

        login_prefix = validate_login_value(payload.login_prefix)
        name_prefix = payload.name_prefix.strip() or "Житель"
        plain_password = validate_password_value(payload.password)

        generated: list[tuple[Apartment, str]] = []
        generated_logins: set[str] = set()
        duplicated_generated_logins: set[str] = set()

        for apartment in target_apartments:
            entrance_number = apartment.entrance.number if apartment.entrance else apartment.entrance_id
            login = f"{login_prefix}{entrance_number}{apartment.apartment_number}".strip()
            if login in generated_logins:
                duplicated_generated_logins.add(login)
            generated_logins.add(login)
            generated.append((apartment, login))

        if duplicated_generated_logins:
            items = ", ".join(sorted(duplicated_generated_logins))
            raise HTTPException(status_code=400, detail=f"Настройки дают одинаковые логины: {items}")

        existing_logins = {
            value
            for value in generated_logins
            if self.user_repo.get_by_login_or_phone(value)
        }
        if existing_logins:
            items = ", ".join(sorted(existing_logins))
            raise HTTPException(status_code=409, detail=f"Логин занят: {items}")

        password_hash = get_password_hash(plain_password)
        created_logins: list[str] = []

        for apartment, login in generated:
            user = User(
                full_name=f"{name_prefix} кв. {apartment.apartment_number}",
                login=login,
                phone=login,
                contact_phone=None,
                password_hash=password_hash,
                role=UserRole.RESIDENT,
                house_id=apartment.house_id,
                apartment_id=apartment.id,
                apartment=apartment.apartment_number,
            )
            self.db.add(user)
            created_logins.append(login)

        self.db.commit()
        return {
            "created_count": len(created_logins),
            "skipped_occupied_count": skipped_occupied_count,
            "created_logins": created_logins,
        }
