from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_current_user
from app.models.user import User
from app.schemas.house_info import (
    EmergencyContactCreate,
    EmergencyContactResponse,
    HouseEventCreate,
    HouseEventResponse,
    HouseScheduleCreate,
    HouseScheduleResponse,
)
from app.services.house_info_service import HouseInfoService

router = APIRouter()


@router.get("/events", response_model=List[HouseEventResponse])
def read_house_events(
    house_id: int | None = None,
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = HouseInfoService(db)
    return service.get_events(current_user, house_id=house_id, active_only=active_only)


@router.post("/events", response_model=HouseEventResponse)
def create_house_event(
    payload: HouseEventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = HouseInfoService(db)
    return service.create_event(current_user, payload)


@router.patch("/events/{event_id}", response_model=HouseEventResponse)
def update_house_event(
    event_id: int,
    payload: HouseEventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = HouseInfoService(db)
    return service.update_event(current_user, event_id, payload)


@router.delete("/events/{event_id}")
def delete_house_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = HouseInfoService(db)
    return service.delete_event(current_user, event_id)


@router.get("/contacts", response_model=List[EmergencyContactResponse])
def read_emergency_contacts(
    house_id: int | None = None,
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = HouseInfoService(db)
    return service.get_contacts(current_user, house_id=house_id, active_only=active_only)


@router.post("/contacts", response_model=EmergencyContactResponse)
def create_emergency_contact(
    payload: EmergencyContactCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = HouseInfoService(db)
    return service.create_contact(current_user, payload)


@router.patch("/contacts/{contact_id}", response_model=EmergencyContactResponse)
def update_emergency_contact(
    contact_id: int,
    payload: EmergencyContactCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = HouseInfoService(db)
    return service.update_contact(current_user, contact_id, payload)


@router.delete("/contacts/{contact_id}")
def delete_emergency_contact(
    contact_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = HouseInfoService(db)
    return service.delete_contact(current_user, contact_id)


@router.get("/schedules", response_model=List[HouseScheduleResponse])
def read_house_schedules(
    house_id: int | None = None,
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = HouseInfoService(db)
    return service.get_schedules(current_user, house_id=house_id, active_only=active_only)


@router.post("/schedules", response_model=HouseScheduleResponse)
def create_house_schedule(
    payload: HouseScheduleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = HouseInfoService(db)
    return service.create_schedule(current_user, payload)


@router.patch("/schedules/{schedule_id}", response_model=HouseScheduleResponse)
def update_house_schedule(
    schedule_id: int,
    payload: HouseScheduleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = HouseInfoService(db)
    return service.update_schedule(current_user, schedule_id, payload)


@router.delete("/schedules/{schedule_id}")
def delete_house_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = HouseInfoService(db)
    return service.delete_schedule(current_user, schedule_id)