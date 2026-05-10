from datetime import datetime
from pydantic import BaseModel, Field

from app.models.remark import RemarkStatus


class RemarkUserMini(BaseModel):
    id: int
    full_name: str
    role: str | None = None
    specialty: str | None = None

    class Config:
        from_attributes = True


class RemarkCreate(BaseModel):
    executor_id: int = Field(..., gt=0)
    comment: str = Field(..., min_length=1, max_length=4000)


class RemarkResponse(BaseModel):
    id: int
    issuer_id: int
    executor_id: int
    comment: str
    status: RemarkStatus
    created_at: datetime
    canceled_at: datetime | None = None
    canceled_by_id: int | None = None

    issuer: RemarkUserMini
    executor: RemarkUserMini
    canceled_by: RemarkUserMini | None = None

    class Config:
        from_attributes = True
