from sqlalchemy.ext.asyncio import AsyncSession
from app.db.operations import run_db

from inspect import signature

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.core.security import create_access_token
from app.core.rate_limit import consume_auth_attempt
from app.services.user_service import UserService

router = APIRouter()


def _call_authenticate(user_service: UserService, identifier: str, password: str):
    """
    Совместимый вызов authenticate().
    В проекте сигнатура UserService.authenticate() менялась:
    где-то использовались phone/password,
    где-то username/password,
    где-то login/password.

    Этот helper смотрит, какие аргументы реально поддерживает текущий UserService,
    и передаёт только их.
    """
    auth_fn = user_service.authenticate
    params = signature(auth_fn).parameters

    kwargs = {}

    if "username" in params:
        kwargs["username"] = identifier
    if "login" in params:
        kwargs["login"] = identifier
    if "phone" in params:
        kwargs["phone"] = identifier
    if "identifier" in params:
        kwargs["identifier"] = identifier
    if "password" in params:
        kwargs["password"] = password

    if not kwargs:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="UserService.authenticate has unsupported signature"
        )

    return auth_fn(**kwargs)


@router.post("/login")
async def login_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    await consume_auth_attempt("login-ip", request.client.host if request.client else "unknown", 60, 60)
    await consume_auth_attempt("login-account", form_data.username.strip().casefold(), 10, 300)
    def operation(db: Session):
        user_service = UserService(db)

        user = _call_authenticate(
            user_service=user_service,
            identifier=form_data.username,
            password=form_data.password,
        )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный логин или пароль",
                headers={"WWW-Authenticate": "Bearer"},
            )

        access_token = create_access_token(subject=str(user.id), session_version=user.session_version)
        return {
            "access_token": access_token,
            "token_type": "bearer"
        }

    return await run_db(db, operation, None)
