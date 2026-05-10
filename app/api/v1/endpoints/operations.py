from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_current_user
from app.models.user import User, UserRole
from app.schemas.operations import (
    BulkAssignTicketsRequest,
    BulkPlanVisitRequest,
    BulkPriorityUpdateRequest,
    BulkTicketOperationResponse,
    ExecutorLoadResponse,
    ExecutorRecommendationResponse,
    OperationsDashboardResponse,
)
from app.services.operations_service import OperationsService

router = APIRouter()


@router.get("/dashboard", response_model=OperationsDashboardResponse)
def get_operations_dashboard(
    house_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in [UserRole.ADMIN, UserRole.DISPATCHER, UserRole.AUDITOR]:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    service = OperationsService(db)
    return service.get_dashboard(house_id=house_id, current_user=current_user)


@router.get("/executors/load", response_model=list[ExecutorLoadResponse])
def get_executor_load(
    house_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in [UserRole.ADMIN, UserRole.DISPATCHER, UserRole.AUDITOR]:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    service = OperationsService(db)
    return service.get_executor_load(house_id=house_id, current_user=current_user)


@router.get("/executors/recommendations", response_model=list[ExecutorRecommendationResponse])
def get_executor_recommendations(
    house_id: int | None = None,
    category_id: int | None = None,
    top: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in [UserRole.ADMIN, UserRole.DISPATCHER, UserRole.AUDITOR]:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    service = OperationsService(db)
    return service.get_executor_recommendations(
        current_user=current_user,
        house_id=house_id,
        category_id=category_id,
        top=top,
    )


@router.post("/tickets/bulk-assign", response_model=BulkTicketOperationResponse)
def bulk_assign_tickets(
    request: BulkAssignTicketsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in [UserRole.ADMIN, UserRole.DISPATCHER]:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    service = OperationsService(db)
    return service.bulk_assign_tickets(request=request, current_user=current_user)


@router.post("/tickets/bulk-priority", response_model=BulkTicketOperationResponse)
def bulk_update_ticket_priority(
    request: BulkPriorityUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in [UserRole.ADMIN, UserRole.DISPATCHER]:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    service = OperationsService(db)
    return service.bulk_update_priority(request=request, current_user=current_user)


@router.post("/tickets/bulk-plan-visit", response_model=BulkTicketOperationResponse)
def bulk_plan_ticket_visit(
    request: BulkPlanVisitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in [UserRole.ADMIN, UserRole.DISPATCHER]:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    service = OperationsService(db)
    return service.bulk_plan_visit(request=request, current_user=current_user)