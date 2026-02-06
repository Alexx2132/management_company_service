from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.schemas.location import HouseUpdate

from app.api.dependencies import get_db, get_current_user
from app.schemas.location import HouseCreate, HouseResponse
from app.services.house_service import HouseService
from app.models.user import User, UserRole

router = APIRouter()


@router.post("/", response_model=HouseResponse)
def create_house(
        house_in: HouseCreate,
        db: Session = Depends(get_db),
        # Только админ может создавать дома!
        current_user: User = Depends(get_current_user)
):
    if current_user.role != UserRole.ADMIN:
        # Временная заглушка, лучше raise HTTPException(403)
        pass

    service = HouseService(db)
    return service.create_house(house_in)


@router.get("/", response_model=List[HouseResponse])
def read_houses(db: Session = Depends(get_db)):
    service = HouseService(db)
    return service.get_all_houses()


@router.put("/{house_id}", response_model=HouseResponse)
def update_house(
        house_id: int,
        house_in: HouseUpdate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Обновить адрес дома (Только Админ)"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(403, "Not enough permissions")

    service = HouseService(db)
    return service.update_house(house_id, house_in)


@router.delete("/{house_id}")
def delete_house(
        house_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Удалить дом (Только Админ)"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(403, "Not enough permissions")

    service = HouseService(db)
    return service.delete_house(house_id)