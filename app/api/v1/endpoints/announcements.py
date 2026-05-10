from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.models.announcement import Announcement
from app.models.location import HouseEntrance
from app.models.user import User, UserRole
from app.repositories.announcement_repository import AnnouncementRepository
from app.schemas.announcement import AnnouncementCreate, AnnouncementResponse

router = APIRouter()


@router.post("/", response_model=AnnouncementResponse)
def create_announcement(
    announcement_in: AnnouncementCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in [UserRole.ADMIN, UserRole.DISPATCHER]:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    data = announcement_in.model_dump()
    target_house_id = data.get("target_house_id")
    target_entrance_id = data.get("target_entrance_id")

    if target_entrance_id is not None:
        if target_house_id is None:
            raise HTTPException(status_code=400, detail="target_house_id is required when target_entrance_id is set")

        entrance = db.query(HouseEntrance).filter(HouseEntrance.id == target_entrance_id).first()
        if not entrance:
            raise HTTPException(status_code=404, detail="Entrance not found")
        if entrance.house_id != target_house_id:
            raise HTTPException(status_code=400, detail="Entrance does not belong to selected house")

    data["author_id"] = current_user.id
    return AnnouncementRepository(db).create(data)


@router.get("/", response_model=List[AnnouncementResponse])
def read_announcements(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return AnnouncementRepository(db).get_visible_for_user(current_user)


@router.patch("/{id}", response_model=AnnouncementResponse)
def update_announcement(
    id: int,
    is_active: bool,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in [UserRole.ADMIN, UserRole.DISPATCHER]:
        raise HTTPException(status_code=403, detail="Only admin or dispatcher")

    ann = db.query(Announcement).filter(Announcement.id == id).first()
    if not ann:
        raise HTTPException(status_code=404, detail="Announcement not found")

    ann.is_active = is_active
    db.commit()
    db.refresh(ann)
    return ann
