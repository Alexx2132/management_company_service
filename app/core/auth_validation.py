import re

from fastapi import HTTPException


CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")
WHITESPACE_RE = re.compile(r"\s")
VALID_PRIORITIES = {"low", "normal", "high", "emergency"}
CONTACT_PHONE_RE = re.compile(r"^\+7\d{10}$")


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
    if len(value) < 12:
        raise HTTPException(status_code=400, detail="Пароль должен содержать не менее 12 символов")
    if len(value.encode("utf-8")) > 72:
        raise HTTPException(status_code=400, detail="Пароль должен содержать не более 72 байт")
    if CYRILLIC_RE.search(value):
        raise HTTPException(status_code=400, detail="Пароль не должен содержать русские буквы")
    return value


def validate_contact_phone_value(phone: str | None, *, required: bool = False) -> str | None:
    raw = str(phone or "").strip()
    if not raw or raw == "+7":
        if required:
            raise HTTPException(status_code=400, detail="Введите контактный телефон")
        return None

    digits = re.sub(r"\D", "", raw)
    if len(digits) == 10:
        normalized = f"+7{digits}"
    elif len(digits) == 11 and digits.startswith("8"):
        normalized = f"+7{digits[1:]}"
    elif len(digits) == 11 and digits.startswith("7"):
        normalized = f"+{digits}"
    else:
        raise HTTPException(status_code=400, detail="Укажите контактный телефон в формате +79001234567")

    if not CONTACT_PHONE_RE.fullmatch(normalized):
        raise HTTPException(status_code=400, detail="Укажите контактный телефон в формате +79001234567")
    return normalized


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
