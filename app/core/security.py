import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Any
from jose import jwt
from app.core.config import settings


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Проверяет пароль, используя 'bcrypt'.
    Принимает строки, внутри конвертирует в байты.
    """
    # bcrypt требует bytes, поэтому кодируем
    password_byte_enc = plain_password.encode('utf-8')
    hashed_password_byte_enc = hashed_password.encode('utf-8')

    return bcrypt.checkpw(password=password_byte_enc, hashed_password=hashed_password_byte_enc)


def get_password_hash(password: str) -> str:
    """
    Хэширует пароль с солью.
    Возвращает строку (decoded bytes), чтобы сохранить в БД (Text/String).
    """
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_bytes = bcrypt.hashpw(password=pwd_bytes, salt=salt)

    return hashed_bytes.decode('utf-8')


def create_access_token(subject: str | Any) -> str:
    """
    Генерирует JWT.
    Аргумент expires_delta убран, время берется строго из настроек.
    Добавлены claims: iat (issued at), nbf (not before).
    """
    # Используем timezone-aware datetime
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {
        "sub": str(subject),
        "exp": expire,
        "iat": now,  # Время выдачи
        "nbf": now  # Токен не валиден до этого времени
    }

    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt
