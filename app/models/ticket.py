import enum
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.base import Base


class TicketStatus(str, enum.Enum):
    CREATED = "created"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELED = "canceled"
    CLOSED = "closed"


# Совместимость со старым operations-модулем
# Поле priority в таблице сейчас может и не использоваться,
# но сам enum нужен для импортов схем и сервисов.
class TicketPriority(str, enum.Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    EMERGENCY = "emergency"


class TicketFileKind(str, enum.Enum):
    BEFORE = "BEFORE"
    AFTER = "AFTER"
    LEGACY = "LEGACY"


class TicketFile(Base):
    __tablename__ = "ticket_files"

    id = Column(Integer, primary_key=True, index=True)
    file_path = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    kind = Column(
        Enum(TicketFileKind, name="ticketfilekind"),
        nullable=False,
        default=TicketFileKind.LEGACY
    )

    ticket_id = Column(Integer, ForeignKey("tickets.id"))
    ticket = relationship("Ticket", back_populates="files")


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(Enum(TicketStatus), default=TicketStatus.CREATED)
    priority = Column(
        Enum(TicketPriority, name="ticketpriority"),
        nullable=False,
        default=TicketPriority.NORMAL,
    )
    first_response_due_at = Column(DateTime, nullable=True)
    due_at = Column(DateTime, nullable=True)
    planned_visit_at = Column(DateTime, nullable=True)
    assigned_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    done_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    canceled_at = Column(DateTime, nullable=True)
    reopened_count = Column(Integer, nullable=False, default=0)
    last_reopened_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    executor_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    author = relationship("User", back_populates="tickets_created", foreign_keys=[author_id])
    executor = relationship("User", back_populates="tickets_assigned", foreign_keys=[executor_id])

    house_id = Column(Integer, ForeignKey("houses.id"), nullable=True)
    apartment_id = Column(Integer, ForeignKey("apartments.id"), nullable=True, index=True)

    # Старое поле сохраняем для совместимости с текущим mobile/backend-потоком
    apartment = Column(String, nullable=True)
    show_contact_phone = Column(Boolean, nullable=False, default=False)
    is_external_request = Column(Boolean, nullable=False, default=False)
    external_contact_phone = Column(String, nullable=True)

    house = relationship("House", back_populates="tickets")
    apartment_ref = relationship("Apartment", back_populates="tickets")

    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    category = relationship("Category", foreign_keys=[category_id], back_populates="tickets")
    place_category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    place_category = relationship("Category", foreign_keys=[place_category_id], back_populates="place_tickets")

    files = relationship("TicketFile", back_populates="ticket")
    result_comment = Column(Text, nullable=True)

    history = relationship("TicketHistory", back_populates="ticket", order_by="desc(TicketHistory.created_at)")
    comments = relationship("TicketComment", back_populates="ticket", order_by="TicketComment.created_at")
