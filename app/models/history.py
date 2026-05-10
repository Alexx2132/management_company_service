from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.base import Base


class TicketHistory(Base):
    __tablename__ = "ticket_history"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"))
    user_id = Column(Integer, ForeignKey("users.id"))

    old_status = Column(String, nullable=True)
    new_status = Column(String, nullable=False)

    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    ticket = relationship("Ticket", back_populates="history")
    user = relationship("User")

    @property
    def user_name(self):
        if self.user is None:
            return None
        return getattr(self.user, "full_name", None) or getattr(self.user, "login", None)

    @property
    def user_role(self):
        if self.user is None:
            return None
        role = getattr(self.user, "role", None)
        return role.value if hasattr(role, "value") else role
