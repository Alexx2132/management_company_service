from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.models.user import User, UserRole
from app.schemas.executor import (
    ExecutorAnalyticsResponse,
    ExecutorAvailabilityResponse,
    ExecutorCreateRequest,
    ExecutorDayOffCreate,
    ExecutorDayOffResponse,
    ExecutorProfileResponse,
    ExecutorUpdateRequest,
    ExecutorWorkScheduleCreate,
    ExecutorWorkScheduleResponse,
    SpecialtyCreate,
    SpecialtyResponse,
)
from app.services.executor_availability import moscow_today
from app.services.executor_service import ExecutorService
from app.services.permissions import can_create_users, can_manage_executor_schedules, is_staff_like

router = APIRouter()


def _ensure_staff(current_user: User):
    if not is_staff_like(current_user):
        raise HTTPException(status_code=403, detail="Not enough permissions")


def _ensure_admin(current_user: User):
    if not can_manage_executor_schedules(current_user):
        raise HTTPException(status_code=403, detail="Only admin can do this")


def _ensure_can_create_executor(current_user: User):
    if not can_create_users(current_user):
        raise HTTPException(status_code=403, detail="Not enough permissions")


@router.get("/specialties", response_model=List[SpecialtyResponse])
def list_specialties(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _ensure_staff(current_user)
    service = ExecutorService(db)
    return service.list_specialties()


@router.post("/specialties", response_model=SpecialtyResponse)
def create_specialty(
    payload: SpecialtyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _ensure_admin(current_user)
    service = ExecutorService(db)
    return service.create_specialty(payload)


@router.delete("/specialties/{specialty_id}")
def delete_specialty(
    specialty_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _ensure_admin(current_user)
    service = ExecutorService(db)
    service.delete_specialty(specialty_id)
    return {"ok": True}


@router.get("/", response_model=List[ExecutorProfileResponse])
def list_executors(
    house_id: int | None = None,
    active_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _ensure_staff(current_user)
    service = ExecutorService(db)
    return service.list_executors(house_id=house_id, active_only=active_only)


@router.get("/availability", response_model=List[ExecutorAvailabilityResponse])
def list_executor_availability(
    target_date: date | None = None,
    house_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _ensure_staff(current_user)
    service = ExecutorService(db)
    return service.list_availability(target_date=target_date or moscow_today(), house_id=house_id)


@router.get("/me/profile", response_model=ExecutorProfileResponse)
def get_my_executor_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = ExecutorService(db)
    return service.get_executor_for_user(current_user)


@router.patch("/me/profile", response_model=ExecutorProfileResponse)
def update_my_executor_profile(
    payload: ExecutorUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = ExecutorService(db)
    return service.update_own_executor_profile(current_user, payload)


@router.put("/me/schedules", response_model=List[ExecutorWorkScheduleResponse])
def replace_my_executor_schedules(
    payload: List[ExecutorWorkScheduleCreate],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = ExecutorService(db)
    return service.replace_own_work_schedules(current_user, payload)


@router.post("/me/days-off", response_model=ExecutorDayOffResponse)
def create_my_executor_day_off(
    payload: ExecutorDayOffCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = ExecutorService(db)
    return service.add_own_day_off(current_user, payload)


@router.delete("/me/days-off/{day_off_id}")
def delete_my_executor_day_off(
    day_off_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = ExecutorService(db)
    return service.delete_own_day_off(current_user, day_off_id)


@router.get("/{executor_id}", response_model=ExecutorProfileResponse)
def get_executor(
    executor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _ensure_staff(current_user)
    service = ExecutorService(db)
    return service.get_executor(executor_id)


@router.get("/{executor_id}/analytics", response_model=ExecutorAnalyticsResponse)
def get_executor_analytics(
    executor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _ensure_staff(current_user)
    service = ExecutorService(db)
    return service.get_executor_analytics(executor_id)


@router.post("/", response_model=ExecutorProfileResponse)
def create_executor(
    payload: ExecutorCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _ensure_can_create_executor(current_user)
    service = ExecutorService(db)
    return service.create_executor(payload)


@router.patch("/{executor_id}", response_model=ExecutorProfileResponse)
def update_executor(
    executor_id: int,
    payload: ExecutorUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _ensure_admin(current_user)
    service = ExecutorService(db)
    return service.update_executor(executor_id, payload)


@router.put("/{executor_id}/schedules", response_model=List[ExecutorWorkScheduleResponse])
def replace_executor_schedules(
    executor_id: int,
    payload: List[ExecutorWorkScheduleCreate],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _ensure_admin(current_user)
    service = ExecutorService(db)
    return service.replace_work_schedules(executor_id, payload)


@router.get("/{executor_id}/days-off", response_model=List[ExecutorDayOffResponse])
def list_executor_days_off(
    executor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _ensure_staff(current_user)
    service = ExecutorService(db)
    return service.list_day_offs(executor_id)


@router.post("/{executor_id}/days-off", response_model=ExecutorDayOffResponse)
def create_executor_day_off(
    executor_id: int,
    payload: ExecutorDayOffCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _ensure_admin(current_user)
    service = ExecutorService(db)
    return service.add_day_off(executor_id, payload)
