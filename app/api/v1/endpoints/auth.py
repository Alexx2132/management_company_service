from inspect import signature

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.core.security import create_access_token
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
def login_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
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

    access_token = create_access_token(subject=str(user.id))
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }
