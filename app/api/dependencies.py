from typing import AsyncIterator
from fastapi import Depends, HTTPException, Request, status
from urllib.parse import unquote
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


from app.db.session import SessionLocal
from app.core.config import settings
from app.schemas.token import TokenData
from app.models.user import User


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as db:
        yield db


async def get_authenticated_user(
        token: str = Depends(oauth2_scheme),
        db: AsyncSession = Depends(get_db)
) -> User:
    return await authenticate_token(token, db)


async def authenticate_token(token: str, db: AsyncSession) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Сессия истекла или недействительна. Войдите снова.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:

        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise credentials_exception

        token_data = TokenData(user_id=user_id)
        numeric_user_id = int(token_data.user_id)

    except (JWTError, ValueError, TypeError):
        raise credentials_exception


    user = await db.scalar(select(User).where(User.id == numeric_user_id))

    if user is None or payload.get("ver", 0) != user.session_version:
        raise credentials_exception

    return user


def require_password_changed(user: User) -> User:
    if user.must_change_password:
        raise HTTPException(status_code=403, detail={
            "code": "password_change_required",
            "message": "Перед продолжением работы смените временный пароль",
        })
    return user


async def get_current_user(user: User = Depends(get_authenticated_user)) -> User:
    return require_password_changed(user)


async def get_file_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    # Cookie разрешена только для чтения изображений из браузера, не для операций записи.
    authorization = request.headers.get("authorization", "")
    token = authorization[7:] if authorization.lower().startswith("bearer ") else ""
    token = token or unquote(request.cookies.get("uk_token", "")).strip().strip('"')
    return require_password_changed(await authenticate_token(token, db))
