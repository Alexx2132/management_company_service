from datetime import datetime

from pydantic import BaseModel

from app.models.user import UserRole
from app.schemas.location import ApartmentResponse, HouseResponse


class UserBase(BaseModel):
    full_name: str

    # Новый логин
    login: str | None = None

    # Старое поле оставляем для совместимости
    phone: str | None = None

    contact_phone: str | None = None
    role: UserRole = UserRole.RESIDENT

    specialty: str | None = None
    house_id: int | None = None
    apartment_id: int | None = None
    apartment: str | None = None
    can_manage_houses: bool = False
    can_ban_residents: bool = False
    can_create_users: bool = False
    can_manage_executor_schedules: bool = False
    can_manage_service_settings: bool = False
    can_manage_remarks: bool = False
    can_manage_house_info: bool = False
    can_manage_announcements: bool = False


class UserCreate(UserBase):
    password: str


class UserChangePassword(BaseModel):
    old_password: str
    new_password: str


class UserResponse(UserBase):
    id: int
    house: HouseResponse | None = None
    apartment_ref: ApartmentResponse | None = None
    banned_until: datetime | None = None

    class Config:
        from_attributes = True


class UserBan(BaseModel):
    banned_until: datetime | None = None


class UserUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    login: str | None = None
    contact_phone: str | None = None


class UserAdminUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    login: str | None = None
    contact_phone: str | None = None
    role: UserRole | None = None
    specialty: str | None = None
    house_id: int | None = None
    apartment_id: int | None = None
    apartment: str | None = None
    can_manage_houses: bool | None = None
    can_ban_residents: bool | None = None
    can_create_users: bool | None = None
    can_manage_executor_schedules: bool | None = None
    can_manage_service_settings: bool | None = None
    can_manage_remarks: bool | None = None
    can_manage_house_info: bool | None = None
    can_manage_announcements: bool | None = None
