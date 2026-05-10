import enum

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.base import Base


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    DISPATCHER = "dispatcher"
    EXECUTOR = "executor"
    RESIDENT = "resident"
    AUDITOR = "auditor"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)

    # Старое поле пока сохраняем для совместимости
    phone = Column(String, unique=True, index=True, nullable=True)

    # Новый логин для входа
    login = Column(String, unique=True, index=True, nullable=False)

    # Отдельный контактный телефон
    contact_phone = Column(String, nullable=True)

    password_hash = Column(String, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.RESIDENT)

    specialty = Column(String, nullable=True)
    can_manage_houses = Column(Boolean, nullable=False, default=False)
    can_ban_residents = Column(Boolean, nullable=False, default=False)

    house_id = Column(Integer, ForeignKey("houses.id"), nullable=True)
    apartment_id = Column(Integer, ForeignKey("apartments.id"), nullable=True, index=True)

    apartment = Column(String, nullable=True)

    house = relationship("House", back_populates="users")
    apartment_ref = relationship("Apartment", back_populates="residents")

    banned_until = Column(DateTime, nullable=True)

    tickets_created = relationship(
        "Ticket",
        back_populates="author",
        primaryjoin="User.id==Ticket.author_id"
    )

    tickets_assigned = relationship(
        "Ticket",
        back_populates="executor",
        primaryjoin="User.id==Ticket.executor_id"
    )

    notifications = relationship(
        "Notification",
        back_populates="user",
        order_by="desc(Notification.created_at)",
        cascade="all, delete-orphan"
    )

    push_tokens = relationship(
        "PushDeviceToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    executor_profile = relationship(
        "ExecutorProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan"
    )
