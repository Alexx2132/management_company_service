import asyncio
import bcrypt
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from jose import jwt
from app.core.config import settings
from sqlalchemy.util.concurrency import await_only, in_greenlet


def _bcrypt_call(function, *args):
    if in_greenlet():
        return await_only(asyncio.to_thread(function, *args))
    return function(*args)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Проверяет пароль, используя 'bcrypt'.
    Принимает строки, внутри конвертирует в байты.
    """

    password_byte_enc = plain_password.encode('utf-8')
    hashed_password_byte_enc = hashed_password.encode('utf-8')

    try:
        return _bcrypt_call(bcrypt.checkpw, password_byte_enc, hashed_password_byte_enc)
    except ValueError:
        return False


def get_password_hash(password: str) -> str:
    """
    Хэширует пароль с солью.
    Возвращает строку (decoded bytes), чтобы сохранить в БД (Text/String).
    """
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_bytes = _bcrypt_call(bcrypt.hashpw, pwd_bytes, salt)

    return hashed_bytes.decode('utf-8')


def generate_temporary_password() -> str:
    return secrets.token_urlsafe(18)


def revoke_user_sessions(db, user) -> None:
    from sqlalchemy import update
    from app.models.user import User
    from app.models.push_device_token import PushDeviceToken

    # Инкремент выполняется в БД, чтобы параллельные сбросы не теряли отзыв сессии.
    db.execute(update(User).where(User.id == user.id).values(session_version=User.session_version + 1))
    db.query(PushDeviceToken).filter(PushDeviceToken.user_id == user.id).update(
        {PushDeviceToken.is_active: False}, synchronize_session=False,
    )


def create_access_token(subject: str | Any, session_version: int = 0) -> str:
    """
    Генерирует JWT.
    Аргумент expires_delta убран, время берется строго из настроек.
    Добавлены claims: iat (issued at), nbf (not before).
    """

    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {
        "sub": str(subject),
        "exp": expire,
        "iat": now,
        "nbf": now,
        "ver": session_version,
    }

    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt
