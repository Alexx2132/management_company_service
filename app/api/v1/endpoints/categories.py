from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.api.dependencies import get_db, get_current_user
from app.schemas.category import CategoryCreate, CategoryResponse
from app.services.category_service import CategoryService
from app.models.user import User, UserRole

router = APIRouter()


@router.post("/", response_model=CategoryResponse)
def create_category(
        category_in: CategoryCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Создать категорию (Только Админ)"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    service = CategoryService(db)
    return service.create_category(category_in)


@router.get("/", response_model=List[CategoryResponse])
def read_categories(db: Session = Depends(get_db)):
    """Получить список всех категорий (Доступно всем)"""
    service = CategoryService(db)
    return service.get_all()
