from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.db.base import Base


class House(Base):
    __tablename__ = "houses"

    id = Column(Integer, primary_key=True, index=True)
    city = Column(String, nullable=False, default="Default City")
    address = Column(String, unique=True, nullable=False, index=True)

    # Связи
    tickets = relationship("Ticket", back_populates="house")

    # Можно добавить связь с жильцами, если хотите (для проверки при удалении)
    users = relationship("User", back_populates="house")
