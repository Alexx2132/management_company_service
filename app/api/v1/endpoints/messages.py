from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.message import (
    MessageContactResponse,
    MessageConversationCreate,
    MessageConversationResponse,
    MessageCreate,
    MessageMuteRequest,
)
from app.services.message_service import MessageService

router = APIRouter()


@router.get("/contacts", response_model=list[MessageContactResponse])
def list_message_contacts(
    role: str | None = Query(default=None),
    q: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return MessageService(db).list_contacts(current_user, role=role, q=q)


@router.get("/conversations", response_model=list[MessageConversationResponse])
def list_conversations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return MessageService(db).list_conversations(current_user)


@router.post("/conversations", response_model=MessageConversationResponse)
def create_conversation(
    payload: MessageConversationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return MessageService(db).create_or_get_conversation(payload, current_user)


@router.post("/admin", response_model=MessageConversationResponse)
def create_admin_conversation(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return MessageService(db).create_or_get_admin_conversation(current_user)


@router.get("/conversations/{conversation_id}", response_model=MessageConversationResponse)
def get_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return MessageService(db).get_conversation(conversation_id, current_user)


@router.post("/conversations/{conversation_id}/messages", response_model=MessageConversationResponse)
def create_message(
    conversation_id: int,
    payload: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return MessageService(db).create_message(conversation_id, payload, current_user)


@router.patch("/conversations/{conversation_id}/read", response_model=MessageConversationResponse)
def mark_conversation_read(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return MessageService(db).mark_read(conversation_id, current_user)


@router.patch("/conversations/{conversation_id}/mute", response_model=MessageConversationResponse)
def mute_conversation(
    conversation_id: int,
    payload: MessageMuteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return MessageService(db).mute(conversation_id, payload, current_user)
