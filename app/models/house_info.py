from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.base import Base


class HouseInfoType(Base):
    __tablename__ = "house_info_types"
    __table_args__ = (
        UniqueConstraint("type_group", "code", name="uq_house_info_type_group_code"),
    )

    id = Column(Integer, primary_key=True, index=True)
    type_group = Column(String(32), nullable=False, index=True)
    code = Column(String(64), nullable=False, index=True)
    name = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class HouseEvent(Base):
    __tablename__ = "house_events"

    id = Column(Integer, primary_key=True, index=True)
    house_id = Column(Integer, ForeignKey("houses.id"), nullable=True, index=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    event_type = Column(String(64), nullable=False)
    starts_at = Column(DateTime, nullable=False)
    ends_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    house = relationship("House", back_populates="events")
    author = relationship("User", lazy="joined")


class EmergencyContact(Base):
    __tablename__ = "emergency_contacts"

    id = Column(Integer, primary_key=True, index=True)
    house_id = Column(Integer, ForeignKey("houses.id"), nullable=True, index=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    title = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    is_24_7 = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    house = relationship("House", back_populates="emergency_contacts")
    author = relationship("User", lazy="joined")


class HouseSchedule(Base):
    __tablename__ = "house_schedules"

    id = Column(Integer, primary_key=True, index=True)
    house_id = Column(Integer, ForeignKey("houses.id"), nullable=True, index=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    schedule_type = Column(String(64), nullable=False)
    starts_at = Column(DateTime, nullable=True)
    ends_at = Column(DateTime, nullable=True)
    start_time = Column(String(8), nullable=True)
    end_time = Column(String(8), nullable=True)
    frequency_text = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    house = relationship("House", back_populates="schedules")
    author = relationship("User", lazy="joined")
