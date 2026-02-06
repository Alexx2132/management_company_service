from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base import Base


class Announcement(Base):
    __tablename__ = "announcements"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Если NULL — объявление для всех. Если есть ID — только для этого дома.
    target_house_id = Column(Integer, ForeignKey("houses.id"), nullable=True)

    # Автор объявления (обычно Админ или Диспетчер)
    author_id = Column(Integer, ForeignKey("users.id"))
