import enum
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.base import Base


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    ADMIN_ASSISTANT = "admin_assistant"
    DISPATCHER = "dispatcher"
    EXECUTOR = "executor"
    RESIDENT = "resident"
    AUDITOR = "auditor"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    phone = Column(String, unique=True, index=True, nullable=True)
    login = Column(String, unique=True, index=True, nullable=False)
    contact_phone = Column(String, nullable=True)
    password_hash = Column(String, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.RESIDENT)
    specialty = Column(String, nullable=True)
    can_manage_houses = Column(Boolean, nullable=False, default=False)
    can_ban_residents = Column(Boolean, nullable=False, default=False)
    can_create_users = Column(Boolean, nullable=False, default=False)
    can_manage_executor_schedules = Column(Boolean, nullable=False, default=False)
    can_manage_service_settings = Column(Boolean, nullable=False, default=False)
    can_manage_remarks = Column(Boolean, nullable=False, default=False)
    can_manage_house_info = Column(Boolean, nullable=False, default=False)
    can_manage_announcements = Column(Boolean, nullable=False, default=False)
    allowed_ticket_priorities = Column(String(120), nullable=True)
    house_id = Column(Integer, ForeignKey("houses.id"), nullable=True)
    apartment_id = Column(Integer, ForeignKey("apartments.id"), nullable=True, index=True)
    apartment = Column(String, nullable=True)
    banned_until = Column(DateTime, nullable=True)
    ban_reason = Column(Text, nullable=True)

    house = relationship("House", back_populates="users")
    apartment_ref = relationship("Apartment", back_populates="residents")
    tickets_created = relationship(
        "Ticket",
        back_populates="author",
        primaryjoin="User.id==Ticket.author_id",
    )
    tickets_assigned = relationship(
        "Ticket",
        back_populates="executor",
        primaryjoin="User.id==Ticket.executor_id",
    )
    notifications = relationship(
        "Notification",
        back_populates="user",
        order_by="desc(Notification.created_at)",
        cascade="all, delete-orphan",
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
        cascade="all, delete-orphan",
    )

    @property
    def house_address(self) -> str | None:
        return self.house.address if self.house else None

    @property
    def apartment_number(self) -> str | None:
        if self.apartment_ref:
            return self.apartment_ref.apartment_number
        return self.apartment

    @property
    def entrance_number(self) -> int | None:
        return self.apartment_ref.entrance_number if self.apartment_ref else None


class UserChangeHistory(Base):
    __tablename__ = "user_change_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    field_name = Column(String(64), nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", foreign_keys=[user_id])
    actor = relationship("User", foreign_keys=[actor_id])

    @property
    def actor_name(self) -> str | None:
        return self.actor.full_name if self.actor else None


class AnnouncementHistory(Base):
    __tablename__ = "announcement_history"

    id = Column(Integer, primary_key=True, index=True)
    announcement_id = Column(Integer, ForeignKey("announcements.id"), nullable=False, index=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String(32), nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    announcement = relationship("Announcement", back_populates="history")
    actor = relationship("User", foreign_keys=[actor_id])

    @property
    def actor_name(self) -> str | None:
        return self.actor.full_name if self.actor else None
