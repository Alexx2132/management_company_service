from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, db: Session):
        super().__init__(User, db)

    def get_by_phone(self, phone: str) -> User | None:
        return self.db.query(User).filter(User.phone == phone).first()

    def get_by_login(self, login: str) -> User | None:
        return self.db.query(User).filter(User.login == login).first()

    def get_by_login_or_phone(self, value: str) -> User | None:
        return (
            self.db.query(User)
            .filter(or_(User.login == value, User.phone == value))
            .first()
        )