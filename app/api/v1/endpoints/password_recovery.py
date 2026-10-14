from sqlalchemy.ext.asyncio import AsyncSession
from app.db.operations import run_db

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.password_recovery import (
    PasswordRecoveryAccepted,
    PasswordRecoveryCreate,
    PasswordRecoveryDecision,
    PasswordRecoveryApartmentOption,
    PasswordRecoveryHouseOption,
    PasswordRecoveryResetRequest,
    PasswordRecoveryResetResponse,
    PasswordRecoveryResponse,
)
from app.services.password_recovery_service import PasswordRecoveryService

router = APIRouter()


@router.get("/houses", response_model=list[PasswordRecoveryHouseOption])
async def list_password_recovery_houses(
    query: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    def operation(db: Session):
        service = PasswordRecoveryService(db)
        return service.list_house_options(query=query, limit=limit)

    return await run_db(db, operation, list[PasswordRecoveryHouseOption])


@router.get("/houses/{house_id}/apartments", response_model=list[PasswordRecoveryApartmentOption])
async def list_password_recovery_apartments(
    house_id: int,
    db: AsyncSession = Depends(get_db),
):
    def operation(db: Session):
        service = PasswordRecoveryService(db)
        return service.list_apartment_options(house_id)

    return await run_db(db, operation, list[PasswordRecoveryApartmentOption])


@router.post("/requests", response_model=PasswordRecoveryAccepted, status_code=202)
async def create_password_recovery_request(
    payload: PasswordRecoveryCreate,
    db: AsyncSession = Depends(get_db),
):
    def operation(db: Session):
        service = PasswordRecoveryService(db)
        service.create_request(payload)
        return PasswordRecoveryAccepted()

    return await run_db(db, operation, PasswordRecoveryAccepted)


@router.get("/requests", response_model=list[PasswordRecoveryResponse])
async def list_password_recovery_requests(
    status: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    def operation(db: Session):
        service = PasswordRecoveryService(db)
        return service.list_requests(current_user=current_user, status=status, skip=skip, limit=limit)

    return await run_db(db, operation, list[PasswordRecoveryResponse])


@router.get("/requests/{request_id}", response_model=PasswordRecoveryResponse)
async def get_password_recovery_request(
    request_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    def operation(db: Session):
        service = PasswordRecoveryService(db)
        return service.get_request(request_id, current_user=current_user)

    return await run_db(db, operation, PasswordRecoveryResponse)


@router.post("/requests/{request_id}/reset", response_model=PasswordRecoveryResetResponse)
async def reset_password_by_recovery_request(
    request_id: int,
    payload: PasswordRecoveryResetRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    def operation(db: Session):
        service = PasswordRecoveryService(db)
        request_obj, temporary_password = service.reset_password(request_id, payload, current_user=current_user)
        return {"request": request_obj, "temporary_password": temporary_password}

    return await run_db(db, operation, PasswordRecoveryResetResponse)


@router.post("/requests/{request_id}/reject", response_model=PasswordRecoveryResponse)
async def reject_password_recovery_request(
    request_id: int,
    payload: PasswordRecoveryDecision,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    def operation(db: Session):
        service = PasswordRecoveryService(db)
        return service.reject_request(request_id, payload, current_user=current_user)

    return await run_db(db, operation, PasswordRecoveryResponse)
