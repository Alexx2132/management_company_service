from pydantic import BaseModel
from app.models.user import UserRole


# Базовая схема
class UserBase(BaseModel):
    full_name: str
    phone: str
    role: UserRole = UserRole.RESIDENT

    specialty: str | None = None
    house_id: int | None = None
    apartment: str | None = None


# Схема для создания
class UserCreate(UserBase):
    password: str


# Схема для смены пароля
class UserChangePassword(BaseModel):
    old_password: str
    new_password: str


# Схема для ответа
class UserResponse(UserBase):
    id: int

    # Здесь нет списков tickets, чтобы избежать рекурсии

    class Config:
        from_attributes = True
