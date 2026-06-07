import re

from fastapi import HTTPException


CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")
WHITESPACE_RE = re.compile(r"\s")
VALID_PRIORITIES = {"low", "normal", "high", "emergency"}


def validate_login_value(login: str | None) -> str:
    value = str(login or "").strip()
    if not value:
        raise HTTPException(status_code=400, detail="Введите логин")
    if WHITESPACE_RE.search(value):
        raise HTTPException(status_code=400, detail="Логин не должен содержать пробелы")
    if CYRILLIC_RE.search(value):
        raise HTTPException(status_code=400, detail="Логин должен быть указан латинскими символами, цифрами или знаками")
    return value


def validate_password_value(password: str | None) -> str:
    value = str(password or "")
    if not value:
        raise HTTPException(status_code=400, detail="Введите пароль")
    if CYRILLIC_RE.search(value):
        raise HTTPException(status_code=400, detail="Пароль не должен содержать русские буквы")
    return value


def normalize_allowed_priorities(value: str | None) -> str | None:
    if value is None:
        return None
    items = [item.strip().lower() for item in str(value).split(",") if item.strip()]
    if not items:
        return None
    invalid = [item for item in items if item not in VALID_PRIORITIES]
    if invalid:
        raise HTTPException(status_code=400, detail="Выбраны неподдерживаемые приоритеты заявок")
    unique = []
    for item in items:
        if item not in unique:
            unique.append(item)
    if set(unique) == VALID_PRIORITIES:
        return None
    return ",".join(unique)
