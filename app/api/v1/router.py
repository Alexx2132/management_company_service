from fastapi import APIRouter

from app.api.v1.endpoints import (
    analytics,
    announcements,
    auth,
    ban_appeals,
    categories,
    complaints,
    executor_recommendations,
    house_info,
    housing,
    live_updates,
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

router = APIRouter()

router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(ban_appeals.router, prefix="/ban-appeals", tags=["ban-appeals"])
router.include_router(users.router, prefix="/users", tags=["users"])
router.include_router(executors_router, prefix="/executors", tags=["executors"])
router.include_router(executor_recommendations.router, prefix="/executor-recommendations", tags=["executor-recommendations"])
router.include_router(housing.router, prefix="/houses", tags=["housing"])
router.include_router(tickets.router, prefix="/tickets", tags=["tickets"])
router.include_router(ticket_comments.router, prefix="/tickets", tags=["ticket-comments"])
router.include_router(announcements.router, prefix="/announcements", tags=["announcements"])
router.include_router(categories.router, prefix="/categories", tags=["categories"])
router.include_router(complaints.router, prefix="/complaints", tags=["complaints"])
router.include_router(ticket_complaints.router, prefix="/ticket-complaints", tags=["ticket-complaints"])
router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
router.include_router(remarks.router, prefix="/remarks", tags=["remarks"])
router.include_router(house_info.router, prefix="/house-info", tags=["house-info"])
router.include_router(live_updates.router, prefix="/ws", tags=["live-updates"])
router.include_router(operations.router, prefix="/operations", tags=["operations"])
router.include_router(reporting.router, prefix="/reports", tags=["reports"])
router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
router.include_router(settings.router, prefix="/settings", tags=["settings"])
