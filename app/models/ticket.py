import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, Text, Enum, DateTime
from sqlalchemy.orm import relationship
from app.db.base import Base


class TicketStatus(str, enum.Enum):
    CREATED = "created"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELED = "canceled"
    CLOSED = "closed"



class TicketFile(Base):
    __tablename__ = "ticket_files"

    id = Column(Integer, primary_key=True, index=True)
    file_path = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Связь с заявкой
    ticket_id = Column(Integer, ForeignKey("tickets.id"))
    ticket = relationship("Ticket", back_populates="files")


# --------------------------------------------

class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(Enum(TicketStatus), default=TicketStatus.CREATED)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Связи с пользователями
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    executor_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Используем строковые имена для ссылок, чтобы избежать ошибок импорта
    author = relationship("User", back_populates="tickets_created", foreign_keys=[author_id])
    executor = relationship("User", back_populates="tickets_assigned", foreign_keys=[executor_id])

    # Связь с домом
    house_id = Column(Integer, ForeignKey("houses.id"), nullable=True)
    apartment = Column(String, nullable=True)
    house = relationship("House", back_populates="tickets")

    # Связь с категорией
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    category = relationship("Category", back_populates="tickets")

    # Связь с файлами
    files = relationship("TicketFile", back_populates="ticket")
    result_comment = Column(Text, nullable=True)
