from sqlalchemy import Column, DateTime, Integer, String
from app.db.base import Base


class AuthRateLimit(Base):
    __tablename__ = "auth_rate_limits"
    key = Column(String(64), primary_key=True)
    attempts = Column(Integer, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
