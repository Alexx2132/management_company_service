from sqlalchemy.orm import Session
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate
from app.core.security import get_password_hash, verify_password
from app.models.user import User
from fastapi import HTTPException

class UserService:
    def __init__(self, db: Session):
        self.user_repo = UserRepository(db)

    def create_user(self, user_in: UserCreate) -> User:
        existing_user = self.user_repo.get_by_phone(user_in.phone)
        if existing_user:
            raise Exception("User already exists")

        user_data = user_in.model_dump()

        # Хэшируем новым методом (через bcrypt)
        plain_password = user_data.pop("password")
        user_data["password_hash"] = get_password_hash(plain_password)

        return self.user_repo.create(user_data)

    def authenticate(self, phone: str, password: str) -> User | None:
        user = self.user_repo.get_by_phone(phone)
        if not user:
            return None
        # Проверка пароля новым методом
        if not verify_password(password, user.password_hash):
            return None
        return user

    def change_password(self, user_id: int, old_password: str, new_password: str):
        # 1. Получаем пользователя из БД
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # 2. Проверяем старый пароль
        if not verify_password(old_password, user.password_hash):
            raise HTTPException(status_code=400, detail="Incorrect old password")

        # 3. Хэшируем новый пароль
        user.password_hash = get_password_hash(new_password)

        # 4. Сохраняем
        self.user_repo.db.commit()
        return {"status": "password updated"}
