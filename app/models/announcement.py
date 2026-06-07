from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.base import Base


class Announcement(Base):
    __tablename__ = "announcements"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # NULL means the announcement is visible to all houses.
    target_house_id = Column(Integer, ForeignKey("houses.id"), nullable=True)
    # NULL means the announcement is visible to all entrances of the selected house.
    target_entrance_id = Column(Integer, ForeignKey("house_entrances.id"), nullable=True)

    author_id = Column(Integer, ForeignKey("users.id"))
    is_important = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

    house = relationship("House", foreign_keys=[target_house_id])
    entrance = relationship("HouseEntrance", foreign_keys=[target_entrance_id])
    history = relationship("AnnouncementHistory", back_populates="announcement", order_by="AnnouncementHistory.created_at")
