from datetime import datetime

from sqlalchemy import Column, Integer, ForeignKey, Text, DateTime, Boolean
from sqlalchemy.orm import relationship

from app.db.base import Base


class TicketComment(Base):
    __tablename__ = "ticket_comments"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False, index=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    message = Column(Text, nullable=False)
    is_internal = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    ticket = relationship("Ticket", back_populates="comments")
    author = relationship("User", lazy="joined")

    @property
    def author_name(self) -> str | None:
        return self.author.full_name if self.author else None