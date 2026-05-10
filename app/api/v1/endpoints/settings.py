from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.app_settings import AppSettingsResponse, AppSettingsUpdate
from app.services.app_settings_service import AppSettingsService

router = APIRouter()


@router.get("/app", response_model=AppSettingsResponse)
def read_app_settings(
    db: Session = Depends(get_db),
):
    service = AppSettingsService(db)
    return service.get_settings()


@router.patch("/app", response_model=AppSettingsResponse)
def update_app_settings(
    data: AppSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = AppSettingsService(db)
    return service.update_settings(data, current_user)
