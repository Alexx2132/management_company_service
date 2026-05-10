from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.models.user import User, UserRole
from app.schemas.location import (
    ApartmentCreate,
    ApartmentGenerateRequest,
    ApartmentResponse,
    ApartmentUpdate,
    HouseCreate,
    HouseEntranceCreate,
    HouseEntranceResponse,
    HouseEntranceUpdate,
    HouseResponse,
    HouseStructureResponse,
    HouseUpdate,
    HouseWithStructureCreateRequest,
)
from app.services.house_service import HouseService

router = APIRouter()


def _ensure_house_manager(current_user: User):
    if current_user.role == UserRole.ADMIN:
        return
    if current_user.role == UserRole.DISPATCHER and bool(current_user.can_manage_houses):
        return
    raise HTTPException(status_code=403, detail="Not enough permissions")


@router.post("/", response_model=HouseResponse)
def create_house(
    house_in: HouseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _ensure_house_manager(current_user)

    service = HouseService(db)
    return service.create_house(house_in)


@router.post("/with-structure", response_model=HouseStructureResponse)
def create_house_with_structure(
    payload: HouseWithStructureCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _ensure_house_manager(current_user)

    service = HouseService(db)
    return service.create_house_with_structure(payload)


@router.get("/", response_model=List[HouseResponse])
def read_houses(db: Session = Depends(get_db)):
    service = HouseService(db)
    return service.get_all_houses()


@router.get("/{house_id}/structure", response_model=HouseStructureResponse)
def read_house_structure(
    house_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = HouseService(db)
    return service.get_house_structure(house_id)


@router.put("/{house_id}", response_model=HouseResponse)
def update_house(
    house_id: int,
    house_in: HouseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _ensure_house_manager(current_user)

    service = HouseService(db)
    return service.update_house(house_id, house_in)


@router.delete("/{house_id}")
def delete_house(
    house_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _ensure_house_manager(current_user)

    service = HouseService(db)
    return service.delete_house(house_id)


@router.get("/{house_id}/entrances", response_model=List[HouseEntranceResponse])
def read_house_entrances(
    house_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = HouseService(db)
    return service.list_entrances(house_id)


@router.post("/{house_id}/entrances", response_model=HouseEntranceResponse)
def create_house_entrance(
    house_id: int,
    payload: HouseEntranceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _ensure_house_manager(current_user)

    service = HouseService(db)
    return service.create_entrance(house_id, payload)


@router.put("/entrances/{entrance_id}", response_model=HouseEntranceResponse)
def update_house_entrance(
    entrance_id: int,
    payload: HouseEntranceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _ensure_house_manager(current_user)

    service = HouseService(db)
    return service.update_entrance(entrance_id, payload)


@router.delete("/entrances/{entrance_id}")
def delete_house_entrance(
    entrance_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _ensure_house_manager(current_user)

    service = HouseService(db)
    return service.delete_entrance(entrance_id)


@router.get("/{house_id}/apartments", response_model=List[ApartmentResponse])
def read_house_apartments(
    house_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = HouseService(db)
    return service.list_apartments_for_house(house_id)


@router.get("/entrances/{entrance_id}/apartments", response_model=List[ApartmentResponse])
def read_entrance_apartments(
    entrance_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = HouseService(db)
    return service.list_apartments_for_entrance(entrance_id)


@router.post("/entrances/{entrance_id}/apartments", response_model=ApartmentResponse)
def create_entrance_apartment(
    entrance_id: int,
    payload: ApartmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _ensure_house_manager(current_user)

    service = HouseService(db)
    return service.create_apartment(entrance_id, payload)


@router.post("/entrances/{entrance_id}/generate-apartments", response_model=List[ApartmentResponse])
def generate_entrance_apartments(
    entrance_id: int,
    payload: ApartmentGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _ensure_house_manager(current_user)

    service = HouseService(db)
    return service.generate_apartments(entrance_id, payload)


@router.put("/apartments/{apartment_id}", response_model=ApartmentResponse)
def update_apartment(
    apartment_id: int,
    payload: ApartmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _ensure_house_manager(current_user)

    service = HouseService(db)
    return service.update_apartment(apartment_id, payload)


@router.delete("/apartments/{apartment_id}")
def delete_apartment(
    apartment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _ensure_house_manager(current_user)

    service = HouseService(db)
    return service.delete_apartment(apartment_id)
