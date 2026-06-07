from datetime import datetime

from pydantic import BaseModel, Field


class AppSettingsResponse(BaseModel):
    complaint_escalate_after_minutes: int = Field(ge=1, le=360)
    complaint_overdue_after_minutes: int = Field(ge=1, le=360)
    complaint_primary_limit: int = Field(ge=1, le=10)
    app_brand: str = Field(min_length=1, max_length=120)
    login_title: str = Field(min_length=1, max_length=200)
    mobile_login_brand: str = Field(min_length=1, max_length=120)
    mobile_login_title: str = Field(min_length=1, max_length=200)
    mobile_login_subtitle: str = Field(min_length=1, max_length=300)
    login_background_image: str | None = Field(default=None, max_length=500)
    service_rules_text: str = Field(min_length=1, max_length=5000)
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class AppSettingsUpdate(BaseModel):
    complaint_escalate_after_minutes: int | None = Field(default=None, ge=1, le=360)
    complaint_overdue_after_minutes: int | None = Field(default=None, ge=1, le=360)
    complaint_primary_limit: int | None = Field(default=None, ge=1, le=10)
    app_brand: str | None = Field(default=None, min_length=1, max_length=120)
    login_title: str | None = Field(default=None, min_length=1, max_length=200)
    mobile_login_brand: str | None = Field(default=None, min_length=1, max_length=120)
    mobile_login_title: str | None = Field(default=None, min_length=1, max_length=200)
    mobile_login_subtitle: str | None = Field(default=None, min_length=1, max_length=300)
    login_background_image: str | None = Field(default=None, max_length=500)
    service_rules_text: str | None = Field(default=None, min_length=1, max_length=5000)
