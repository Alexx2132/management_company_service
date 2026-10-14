from datetime import datetime

from pydantic import BaseModel, Field

from app.models.user import UserRole


class PasswordRecoveryCreate(BaseModel):
    login: str = Field(..., min_length=1, max_length=120)
    full_name: str | None = Field(default=None, max_length=200)
    contact_phone: str = Field(..., min_length=3, max_length=60)
    house_id: int | None = None
    apartment_id: int | None = None
    house_address: str | None = Field(default=None, max_length=300)
    apartment: str | None = Field(default=None, max_length=40)
    message: str | None = Field(default=None, max_length=1000)


class PasswordRecoveryAccepted(BaseModel):
    message: str = "Если данные относятся к зарегистрированному пользователю, запрос будет рассмотрен"


class PasswordRecoveryHouseOption(BaseModel):
    id: int
    city: str | None = None
    address: str

    class Config:
        from_attributes = True


class PasswordRecoveryApartmentOption(BaseModel):
    id: int
    apartment_number: str
    entrance_number: int | None = None
    floor_number: int | None = None

    class Config:
        from_attributes = True


class PasswordRecoveryUserSummary(BaseModel):
    id: int
    full_name: str
    login: str | None = None
    contact_phone: str | None = None
    role: UserRole
    house_address: str | None = None
    apartment_number: str | None = None

    class Config:
        from_attributes = True


class PasswordRecoveryResponse(BaseModel):
    id: int
    requester_login: str
    requester_name: str | None = None
    contact_phone: str
    house_id: int | None = None
    apartment_id: int | None = None
    house_address: str | None = None
    apartment: str | None = None
    message: str | None = None
    status: str
    verification_status: str | None = None
    verification_note: str | None = None
    matched_user_id: int | None = None
    matched_user: PasswordRecoveryUserSummary | None = None
    processed_by_id: int | None = None
    processed_by_name: str | None = None
    admin_comment: str | None = None
    created_at: datetime
    updated_at: datetime
    processed_at: datetime | None = None

    class Config:
        from_attributes = True


class PasswordRecoveryDecision(BaseModel):
    admin_comment: str | None = Field(default=None, max_length=1000)


class PasswordRecoveryResetRequest(PasswordRecoveryDecision):
    temporary_password: str | None = Field(default=None, max_length=64)


class PasswordRecoveryResetResponse(BaseModel):
    request: PasswordRecoveryResponse
    temporary_password: str
