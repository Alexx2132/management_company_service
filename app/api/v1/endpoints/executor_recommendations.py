from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.models.user import User, UserRole
from app.schemas.executor_recommendation import ExecutorRecommendationResponse
from app.services.executor_recommendation_service import ExecutorRecommendationService

router = APIRouter()


def _ensure_staff(current_user: User):
    if current_user.role not in [UserRole.ADMIN, UserRole.DISPATCHER, UserRole.AUDITOR]:
        raise HTTPException(status_code=403, detail="Not enough permissions")


@router.get("/by-ticket", response_model=List[ExecutorRecommendationResponse])
def recommend_executors_by_ticket(
    ticket_id: int,
    top: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _ensure_staff(current_user)

    service = ExecutorRecommendationService(db)
    return service.recommend_for_ticket(ticket_id=ticket_id, top=top)