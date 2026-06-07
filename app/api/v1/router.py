from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.api.v1.endpoints import (
    analytics,
    announcements,
    auth,
    ban_appeals,
    categories,
    complaints,
    house_info,
    housing,
    live_updates,
    messages,
    notifications,
    operations,
    remarks,
    reporting,
    settings,
    ticket_comments,
    ticket_complaints,
    tickets,
    users,
)
from app.api.v1.endpoints.executors import router as executors_router
from app.models.user import User, UserRole
from app.schemas.executor_recommendation import ExecutorRecommendationResponse
from app.services.executor_service import ExecutorService

router = APIRouter()

router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(ban_appeals.router, prefix="/ban-appeals", tags=["ban-appeals"])
router.include_router(users.router, prefix="/users", tags=["users"])
router.include_router(executors_router, prefix="/executors", tags=["executors"])
router.include_router(housing.router, prefix="/houses", tags=["housing"])
router.include_router(tickets.router, prefix="/tickets", tags=["tickets"])
router.include_router(ticket_comments.router, prefix="/tickets", tags=["ticket-comments"])
router.include_router(announcements.router, prefix="/announcements", tags=["announcements"])
router.include_router(categories.router, prefix="/categories", tags=["categories"])
router.include_router(complaints.router, prefix="/complaints", tags=["complaints"])
router.include_router(ticket_complaints.router, prefix="/ticket-complaints", tags=["ticket-complaints"])
router.include_router(messages.router, prefix="/messages", tags=["messages"])
router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
router.include_router(remarks.router, prefix="/remarks", tags=["remarks"])
router.include_router(house_info.router, prefix="/house-info", tags=["house-info"])
router.include_router(live_updates.router, prefix="/ws", tags=["live-updates"])
router.include_router(operations.router, prefix="/operations", tags=["operations"])
router.include_router(reporting.router, prefix="/reports", tags=["reports"])
router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
router.include_router(settings.router, prefix="/settings", tags=["settings"])


@router.get(
    "/executor-recommendations/by-ticket",
    response_model=list[ExecutorRecommendationResponse],
    tags=["executor-recommendations"],
)
def recommend_executors_by_ticket(
    ticket_id: int,
    top: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in [UserRole.ADMIN, UserRole.DISPATCHER, UserRole.AUDITOR]:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    service = ExecutorService(db)
    return service.recommend_for_ticket(ticket_id=ticket_id, top=top)
