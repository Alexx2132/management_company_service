import enum
from datetime import datetime

from sqlalchemy import Column, Integer, ForeignKey, Text, Enum, DateTime, String
from sqlalchemy.orm import relationship

from app.db.base import Base


class ComplaintType(str, enum.Enum):
    OVERDUE = "OVERDUE"
    QUALITY = "QUALITY"
    DISPATCHER_INACTION = "DISPATCHER_INACTION"


class ComplaintStatus(str, enum.Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


class TicketComplaint(Base):
    __tablename__ = "ticket_complaints"

    id = Column(Integer, primary_key=True, index=True)

    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    parent_complaint_id = Column(Integer, ForeignKey("ticket_complaints.id"), nullable=True)

    complaint_type = Column(Enum(ComplaintType, name="complainttype"), nullable=False)
    description = Column(Text, nullable=True)

    status = Column(Enum(ComplaintStatus, name="complaintstatus"), default=ComplaintStatus.OPEN, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    resolver_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolution_comment = Column(Text, nullable=True)

    ticket = relationship("Ticket", lazy="joined")
    author = relationship("User", foreign_keys=[author_id], lazy="joined")
    resolver = relationship("User", foreign_keys=[resolver_id], lazy="joined")
    parent_complaint = relationship("TicketComplaint", remote_side=[id], lazy="joined")

    files = relationship("ComplaintFile", back_populates="complaint", cascade="all, delete-orphan")
    comments = relationship(
        "ComplaintComment",
        back_populates="complaint",
        cascade="all, delete-orphan",
        order_by="ComplaintComment.created_at"
    )

    @property
    def author_name(self):
        return self.author.full_name if self.author else None

    @property
    def resolver_name(self):
        return self.resolver.full_name if self.resolver else None

    @property
    def resolver_role(self):
        if not self.resolver or self.resolver.role is None:
            return None
        return self.resolver.role.value if hasattr(self.resolver.role, "value") else str(self.resolver.role)


class ComplaintFile(Base):
    __tablename__ = "complaint_files"

    id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(Integer, ForeignKey("ticket_complaints.id"), nullable=False)

    file_path = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    complaint = relationship("TicketComplaint", back_populates="files")


class ComplaintComment(Base):
    __tablename__ = "complaint_comments"

    id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(Integer, ForeignKey("ticket_complaints.id"), nullable=False, index=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    complaint = relationship("TicketComplaint", back_populates="comments")
    author = relationship("User", lazy="joined")

    @property
    def author_name(self):
        return self.author.full_name if self.author else None

    @property
    def author_role(self):
        if not self.author or self.author.role is None:
            return None
        return self.author.role.value if hasattr(self.author.role, "value") else str(self.author.role)
