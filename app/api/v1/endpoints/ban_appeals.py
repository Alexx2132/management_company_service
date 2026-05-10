from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.ban_appeal import BanConversationResponse, BanMessageCreate
from app.services.ban_appeal_service import BanAppealService

router = APIRouter()


@router.get("/my", response_model=BanConversationResponse)
def get_my_ban_conversation(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return BanAppealService(db).get_my_conversation(current_user)


@router.post("/my/messages", response_model=BanConversationResponse)
def create_my_ban_message(
    payload: BanMessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return BanAppealService(db).add_message_to_my_conversation(payload, current_user)


@router.get("/", response_model=list[BanConversationResponse])
def list_ban_conversations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return BanAppealService(db).list_conversations(current_user)


@router.get("/{conversation_id}", response_model=BanConversationResponse)
def get_ban_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return BanAppealService(db).get_conversation(conversation_id, current_user)


@router.post("/{conversation_id}/messages", response_model=BanConversationResponse)
def create_ban_message(
    conversation_id: int,
    payload: BanMessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return BanAppealService(db).add_message(conversation_id, payload, current_user)
