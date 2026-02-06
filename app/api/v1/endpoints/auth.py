from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.services.user_service import UserService
from app.core.security import create_access_token
from app.schemas.token import Token

router = APIRouter()


@router.post("/login", response_model=Token)
def login_access_token(
        db: Session = Depends(get_db),
        form_data: OAuth2PasswordRequestForm = Depends()
):
    user_service = UserService(db)
    # form_data.username - это phone
    user = user_service.authenticate(phone=form_data.username, password=form_data.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect phone or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # ИЗМЕНЕНИЕ: Больше не передаем timedelta, функция сама берет настройки
    access_token = create_access_token(subject=user.id)

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }
