import enum
from datetime import datetime

from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship

from app.db.base import Base


class RemarkStatus(str, enum.Enum):
    ACTIVE = "active"
    CANCELED = "canceled"


class Remark(Base):
    __tablename__ = "remarks"

    id = Column(Integer, primary_key=True, index=True)

    issuer_id = Column(Integer, ForeignKey("users.id"), nullable=False)     # кто вынес (dispatcher/auditor)
    executor_id = Column(Integer, ForeignKey("users.id"), nullable=False)   # кому (executor)

    comment = Column(Text, nullable=False)

    status = Column(Enum(RemarkStatus), nullable=False, default=RemarkStatus.ACTIVE)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    canceled_at = Column(DateTime, nullable=True)
    canceled_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    issuer = relationship("User", foreign_keys=[issuer_id])
    executor = relationship("User", foreign_keys=[executor_id])
    canceled_by = relationship("User", foreign_keys=[canceled_by_id])