from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.models.announcement import Announcement
from app.models.location import Apartment, HouseEntrance
from app.models.user import User, UserRole
from app.repositories.announcement_repository import AnnouncementRepository
from app.schemas.announcement import AnnouncementCreate, AnnouncementResponse
from app.services.notification_service import NotificationService
from app.services.permissions import can_manage_announcements

router = APIRouter()


def _announcement_target_resident_ids(
    db: Session,
    target_house_id: int | None,
    target_entrance_id: int | None,
) -> list[int]:
    query = db.query(User.id).filter(User.role == UserRole.RESIDENT)

    if target_house_id is not None:
        query = query.filter(User.house_id == target_house_id)

    if target_entrance_id is not None:
        query = (
            query
            .join(Apartment, User.apartment_id == Apartment.id)
            .filter(Apartment.entrance_id == target_entrance_id)
        )

    return [row[0] for row in query.all()]


@router.post("/", response_model=AnnouncementResponse)
def create_announcement(
    announcement_in: AnnouncementCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not can_manage_announcements(current_user):
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
    announcement = AnnouncementRepository(db).create(data)
    target_ids = _announcement_target_resident_ids(db, target_house_id, target_entrance_id)
    NotificationService(db).notify_many(
        user_ids=target_ids,
        title="Новое объявление",
        message=announcement.title,
        notif_type="announcement",
        announcement_id=announcement.id,
    )
    return announcement


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
    if not can_manage_announcements(current_user):
        raise HTTPException(status_code=403, detail="Not enough permissions")

    ann = db.query(Announcement).filter(Announcement.id == id).first()
    if not ann:
        raise HTTPException(status_code=404, detail="Announcement not found")
    if ann.author_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only announcement author can archive it")

    ann.is_active = is_active
    db.commit()
    db.refresh(ann)
    return ann
