import enum
from sqlalchemy import Column, Integer, String, ForeignKey, Enum
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
    phone = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.RESIDENT)

    specialty = Column(String, nullable=True)

    house_id = Column(Integer, ForeignKey("houses.id"), nullable=True)
    apartment = Column(String, nullable=True)

    house = relationship("House", back_populates="users")

    # --- ИСПРАВЛЕННЫЕ СТРОКИ ---
    # Используем primaryjoin в виде строки. Это решает проблему "Ticket is not defined"
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
    # ---------------------------
