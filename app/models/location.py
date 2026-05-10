from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class House(Base):
    __tablename__ = "houses"

    id = Column(Integer, primary_key=True, index=True)
    city = Column(String, nullable=False, default="Default City")
    address = Column(String, unique=True, nullable=False, index=True)

    tickets = relationship("Ticket", back_populates="house")
    users = relationship("User", back_populates="house")

    events = relationship("HouseEvent", back_populates="house")
    emergency_contacts = relationship("EmergencyContact", back_populates="house")
    schedules = relationship("HouseSchedule", back_populates="house")

    entrances = relationship(
        "HouseEntrance",
        back_populates="house",
        cascade="all, delete-orphan",
        order_by="HouseEntrance.number",
    )
    apartments = relationship(
        "Apartment",
        back_populates="house",
        cascade="all, delete-orphan",
    )


class HouseEntrance(Base):
    __tablename__ = "house_entrances"
    __table_args__ = (
        UniqueConstraint("house_id", "number", name="uq_house_entrances_house_number"),
    )

    id = Column(Integer, primary_key=True, index=True)
    house_id = Column(Integer, ForeignKey("houses.id"), nullable=False, index=True)

    number = Column(Integer, nullable=False)
    floors_count = Column(Integer, nullable=False, default=0)
    apartments_count = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    house = relationship("House", back_populates="entrances")
    apartments = relationship(
        "Apartment",
        back_populates="entrance",
        cascade="all, delete-orphan",
    )


class Apartment(Base):
    __tablename__ = "apartments"
    __table_args__ = (
        UniqueConstraint("house_id", "apartment_number", name="uq_apartments_house_apartment_number"),
    )

    id = Column(Integer, primary_key=True, index=True)
    house_id = Column(Integer, ForeignKey("houses.id"), nullable=False, index=True)
    entrance_id = Column(Integer, ForeignKey("house_entrances.id"), nullable=False, index=True)

    floor_number = Column(Integer, nullable=False)
    apartment_number = Column(String, nullable=False)
    rooms_count = Column(Integer, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    house = relationship("House", back_populates="apartments")
    entrance = relationship("HouseEntrance", back_populates="apartments")

    residents = relationship("User", back_populates="apartment_ref")
    tickets = relationship("Ticket", back_populates="apartment_ref")