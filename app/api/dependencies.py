from typing import Generator
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session

# Импорты наших модулей
from app.db.session import SessionLocal
from app.core.config import settings
from app.schemas.token import TokenData
from app.models.user import User
from app.repositories.user_repository import UserRepository

# Указываем URL для получения токена (для Swagger UI)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
        token: str = Depends(oauth2_scheme),
        db: Session = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # Декодируем токен
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise credentials_exception

        token_data = TokenData(user_id=user_id)

    except JWTError:
        raise credentials_exception

    # Проверяем пользователя в БД
    user_repo = UserRepository(db)
    # Важно: конвертируем user_id в int, так как в БД id - это Integer
    user = user_repo.get_by_id(int(token_data.user_id))

    if user is None:
        raise credentials_exception

    return user
