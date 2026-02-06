from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.api.dependencies import get_db, get_current_user
from app.schemas.announcement import AnnouncementCreate, AnnouncementResponse
from app.models.user import User, UserRole
from app.repositories.announcement_repository import AnnouncementRepository

router = APIRouter()


@router.post("/", response_model=AnnouncementResponse)
def create_announcement(
        announcement_in: AnnouncementCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    # Только персонал может создавать
    if current_user.role not in [UserRole.ADMIN, UserRole.DISPATCHER]:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    repo = AnnouncementRepository(db)

    # Добавляем ID автора вручную
    data = announcement_in.model_dump()
    data["author_id"] = current_user.id

    return repo.create(data)


@router.get("/", response_model=List[AnnouncementResponse])
def read_announcements(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    repo = AnnouncementRepository(db)
    return repo.get_visible_for_user(current_user)
