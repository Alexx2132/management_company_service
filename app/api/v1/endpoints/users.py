from fastapi import APIRouter, Depends, HTTPException  # <-- Добавили HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.api.dependencies import get_db, get_current_user
from app.schemas.user import UserCreate, UserResponse, UserChangePassword
from app.services.user_service import UserService
from app.models.user import User, UserRole

router = APIRouter()


@router.post("/", response_model=UserResponse)
def create_user(user_in: UserCreate, db: Session = Depends(get_db)):
    user_service = UserService(db)
    return user_service.create_user(user_in)


@router.post("/me/password")
def change_password(
        password_data: UserChangePassword,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Сменить свой пароль"""
    service = UserService(db)
    return service.change_password(
        user_id=current_user.id,
        old_password=password_data.old_password,
        new_password=password_data.new_password
    )


@router.get("/me", response_model=UserResponse)
def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user


# --- НОВЫЙ ЭНДПОИНТ: Список всех пользователей ---
@router.get("/", response_model=List[UserResponse])
def read_all_users(
        skip: int = 0,
        limit: int = 100,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """
    Получить список всех пользователей.
    Доступно: Админам, Диспетчерам и АУДИТОРАМ.
    """
    # Вот та самая проверка, про которую я говорил:
    if current_user.role not in [UserRole.ADMIN, UserRole.DISPATCHER, UserRole.AUDITOR]:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    # Прямое обращение к репозиторию для простоты (или можно добавить метод в Service)
    from app.repositories.user_repository import UserRepository
    repo = UserRepository(db)
    return repo.get_all(skip=skip, limit=limit)
