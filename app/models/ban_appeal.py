from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.base import Base


class BanConversation(Base):
    __tablename__ = "ban_conversations"
    __table_args__ = (UniqueConstraint("resident_id", name="uq_ban_conversations_resident_id"),)

    id = Column(Integer, primary_key=True, index=True)
    resident_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    resident = relationship("User", foreign_keys=[resident_id])
    messages = relationship(
        "BanMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="BanMessage.created_at",
    )


class BanMessage(Base):
    __tablename__ = "ban_messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("ban_conversations.id"), nullable=False, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    conversation = relationship("BanConversation", back_populates="messages")
    sender = relationship("User", foreign_keys=[sender_id])
