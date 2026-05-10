from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.base import Base


class PushDeviceToken(Base):
    __tablename__ = "push_device_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token = Column(String(512), nullable=False, unique=True, index=True)
    platform = Column(String(32), nullable=False, default="android")
    role = Column(String(32), nullable=False, index=True)
    device_name = Column(String(160), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    last_seen_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="push_tokens")
