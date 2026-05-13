from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.category import CategoryCreate, CategoryResponse
from app.services.category_service import CategoryService
from app.services.permissions import can_manage_service_settings

router = APIRouter()


@router.post("/", response_model=CategoryResponse)
def create_category(
    category_in: CategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not can_manage_service_settings(current_user):
        raise HTTPException(status_code=403, detail="Not enough permissions")

    service = CategoryService(db)
    return service.create_category(category_in)


@router.get("/", response_model=List[CategoryResponse])
def read_categories(category_type: str | None = "problem", db: Session = Depends(get_db)):
    service = CategoryService(db)
    return service.get_all(category_type=category_type)


@router.delete("/{category_id}")
def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not can_manage_service_settings(current_user):
        raise HTTPException(status_code=403, detail="Not enough permissions")

    service = CategoryService(db)
    return service.delete_category(category_id)
