from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.models.user import User, UserRole
from app.schemas.analytics import TicketAnalyticsOverviewResponse
from app.services.analytics_service import AnalyticsService

router = APIRouter()


def _ensure_staff(current_user: User):
    if current_user.role not in [UserRole.ADMIN, UserRole.DISPATCHER, UserRole.AUDITOR]:
        raise HTTPException(status_code=403, detail="Not enough permissions")


@router.get("/tickets/overview", response_model=TicketAnalyticsOverviewResponse)
def get_ticket_overview(
    house_id: int | None = None,
    category_id: int | None = None,
    place_category_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _ensure_staff(current_user)

    service = AnalyticsService(db)
    return service.get_ticket_overview(
        house_id=house_id,
        category_id=category_id,
        place_category_id=place_category_id,
        date_from=date_from,
        date_to=date_to
    )
