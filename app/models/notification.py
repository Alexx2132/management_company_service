from datetime import datetime

from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, DateTime, Text
from sqlalchemy.orm import relationship

from app.db.base import Base


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    notif_type = Column(String, nullable=False)

    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=True)
    complaint_id = Column(Integer, ForeignKey("ticket_complaints.id"), nullable=True)
    announcement_id = Column(Integer, ForeignKey("announcements.id"), nullable=True)

    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    read_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="notifications")
