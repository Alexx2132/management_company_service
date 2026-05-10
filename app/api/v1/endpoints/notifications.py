from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.notification import (
    NotificationResponse,
    NotificationSummaryResponse,
    PushDeviceTokenResponse,
    PushTokenDeactivateRequest,
    PushTokenRegisterRequest,
)
from app.services.notification_service import NotificationService
from app.services.push_notification_service import PushNotificationService

router = APIRouter()


@router.get("/", response_model=list[NotificationResponse])
def list_my_notifications(
    unread_only: bool = False,
    notif_type: str | None = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = NotificationService(db)
    return service.list_my(
        current_user.id,
        unread_only=unread_only,
        notif_type=notif_type,
        skip=skip,
        limit=limit,
    )


@router.get("/summary", response_model=NotificationSummaryResponse)
def get_notifications_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = NotificationService(db)
    return service.get_summary(current_user.id)


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = NotificationService(db)
    return service.mark_read(current_user.id, notification_id)


@router.patch("/read-all")
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = NotificationService(db)
    count = service.mark_all_read(current_user.id)
    return {"status": "ok", "marked": count}


@router.post("/push-token", response_model=PushDeviceTokenResponse)
def register_push_token(
    payload: PushTokenRegisterRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = PushNotificationService(db)
    return service.register_token(
        user=current_user,
        token=payload.token,
        platform=payload.platform,
        device_name=payload.device_name,
    )


@router.delete("/push-token")
def deactivate_push_token(
    payload: PushTokenDeactivateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = PushNotificationService(db)
    deactivated = service.deactivate_token(current_user, payload.token)
    return {"status": "ok", "deactivated": deactivated}
