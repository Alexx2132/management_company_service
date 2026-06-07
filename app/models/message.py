from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.base import Base


class MessageConversation(Base):
    __tablename__ = "message_conversations"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(220), nullable=True)
    context_type = Column(String(32), nullable=False, default="direct")
    direct_key = Column(String(80), nullable=True, unique=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=True, index=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    is_closed = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    created_by = relationship("User", foreign_keys=[created_by_id])
    ticket = relationship("Ticket", foreign_keys=[ticket_id])
    participants = relationship(
        "MessageParticipant",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="MessageParticipant.id",
    )
    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )


class MessageParticipant(Base):
    __tablename__ = "message_participants"
    __table_args__ = (UniqueConstraint("conversation_id", "user_id", name="uq_message_participant"),)

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("message_conversations.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    muted_until = Column(DateTime, nullable=True)
    last_read_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    conversation = relationship("MessageConversation", back_populates="participants")
    user = relationship("User", foreign_keys=[user_id])


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("message_conversations.id"), nullable=False, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    conversation = relationship("MessageConversation", back_populates="messages")
    sender = relationship("User", foreign_keys=[sender_id])
    files = relationship(
        "MessageFile",
        back_populates="message",
        cascade="all, delete-orphan",
        order_by="MessageFile.id",
    )


class MessageFile(Base):
    __tablename__ = "message_files"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("messages.id"), nullable=False, index=True)
    file_url = Column(String(500), nullable=False)
    original_filename = Column(String(255), nullable=True)
    content_type = Column(String(120), nullable=True)
    size_bytes = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    message = relationship("Message", back_populates="files")
