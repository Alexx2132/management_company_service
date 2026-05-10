from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.models.location import Apartment
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository
from app.schemas.user import (
    UserAdminUpdate,
    UserBan,
    UserChangePassword,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from app.services.user_service import UserService

router = APIRouter()


@router.post("/", response_model=UserResponse)
def create_user(
        user_in: UserCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Only admin can create users")

    user_service = UserService(db)
    return user_service.create_user(user_in)


@router.post("/me/password")
def change_password(
        password_data: UserChangePassword,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    service = UserService(db)
    return service.change_password(
        user_id=current_user.id,
        old_password=password_data.old_password,
        new_password=password_data.new_password
    )


@router.get("/me", response_model=UserResponse)
def read_users_me(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if (
        current_user.role == UserRole.RESIDENT
        and current_user.house_id is not None
        and current_user.apartment_id is None
        and current_user.apartment
    ):
        apartment = (
            db.query(Apartment)
            .filter(
                Apartment.house_id == current_user.house_id,
                Apartment.apartment_number == str(current_user.apartment),
                Apartment.is_active.is_(True),
            )
            .first()
        )
        if apartment:
            current_user.apartment_id = apartment.id
            db.commit()
            db.refresh(current_user)
    return current_user


@router.patch("/me", response_model=UserResponse)
def update_user_me(
    user_in: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = UserService(db)
    return service.update_user(current_user.id, user_in)


@router.patch("/{user_id}", response_model=UserResponse)
def admin_update_user(
        user_id: int,
        user_in: UserAdminUpdate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    service = UserService(db)
    return service.admin_update_user(user_id, user_in, current_user)


@router.get("/", response_model=List[UserResponse])
def read_all_users(
        skip: int = 0,
        limit: int = 100,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    if current_user.role not in [UserRole.ADMIN, UserRole.DISPATCHER, UserRole.AUDITOR]:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    if current_user.role == UserRole.DISPATCHER:
        return (
            db.query(User)
            .filter(User.role.in_([UserRole.RESIDENT, UserRole.DISPATCHER]))
            .offset(skip)
            .limit(limit)
            .all()
        )

    repo = UserRepository(db)
    return repo.get_all(skip=skip, limit=limit)


@router.get("/residents", response_model=List[UserResponse])
def read_residents(
        house_id: int | None = None,
        entrance_id: int | None = None,
        apartment_id: int | None = None,
        skip: int = 0,
        limit: int = 200,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    if current_user.role not in [UserRole.ADMIN, UserRole.DISPATCHER, UserRole.AUDITOR]:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    q = db.query(User).filter(User.role == UserRole.RESIDENT)

    if house_id is not None:
        q = q.filter(User.house_id == house_id)

    if entrance_id is not None:
        q = q.join(Apartment, User.apartment_id == Apartment.id).filter(Apartment.entrance_id == entrance_id)

    if apartment_id is not None:
        q = q.filter(User.apartment_id == apartment_id)

    return q.offset(skip).limit(limit).all()


@router.get("/executors", response_model=List[UserResponse])
def read_executors(
        house_id: int | None = None,
        skip: int = 0,
        limit: int = 200,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    if current_user.role not in [UserRole.ADMIN, UserRole.DISPATCHER, UserRole.AUDITOR]:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    effective_house_id = house_id
    if current_user.role == UserRole.DISPATCHER and effective_house_id is None:
        effective_house_id = current_user.house_id

    q = db.query(User).filter(User.role == UserRole.EXECUTOR)

    if effective_house_id is not None:
        q = q.filter((User.house_id == effective_house_id) | (User.house_id.is_(None)))

    return q.offset(skip).limit(limit).all()


@router.post("/{user_id}/ban")
def ban_user(
    user_id: int,
    ban_data: UserBan,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = UserService(db)
    return service.ban_user(user_id, ban_data, current_user)
