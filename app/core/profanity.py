from __future__ import annotations

import re
import unicodedata

from fastapi import HTTPException


PROFANITY_ERROR = "Используются недопустимые выражения. Пожалуйста, измените текст."


_CHAR_MAP = str.maketrans(
    {
        "ё": "е",
        "0": "о",
        "1": "и",
        "3": "е",
        "4": "а",
        "5": "с",
        "6": "б",
        "7": "т",
        "@": "а",
        "$": "с",
    }
)

_WORD_CHARS = r"0-9a-zа-я"

_TOKEN_PATTERNS = [
    rf"(?:бля|блять|бляд[{_WORD_CHARS}]*|сук[{_WORD_CHARS}]*|суч[{_WORD_CHARS}]*|мраз[{_WORD_CHARS}]*|гандон[{_WORD_CHARS}]*|говн[{_WORD_CHARS}]*|дерьм[{_WORD_CHARS}]*|мудак[{_WORD_CHARS}]*|долбо[{_WORD_CHARS}]*)",
    rf"(?:хуй|хуе[{_WORD_CHARS}]*|хуя[{_WORD_CHARS}]*|хер[{_WORD_CHARS}]*|пизд[{_WORD_CHARS}]*|пидор[{_WORD_CHARS}]*|пидар[{_WORD_CHARS}]*)",
    rf"(?:еба[{_WORD_CHARS}]*|еби[{_WORD_CHARS}]*|ебу[{_WORD_CHARS}]*|ебл[{_WORD_CHARS}]*|ебн[{_WORD_CHARS}]*|ебт[{_WORD_CHARS}]*|выеб[{_WORD_CHARS}]*|заеб[{_WORD_CHARS}]*|наеб[{_WORD_CHARS}]*|отъеб[{_WORD_CHARS}]*|поеб[{_WORD_CHARS}]*|проеб[{_WORD_CHARS}]*|разъеб[{_WORD_CHARS}]*|съеб[{_WORD_CHARS}]*)",
    rf"(?:дебил[{_WORD_CHARS}]*|идиот[{_WORD_CHARS}]*|урод[{_WORD_CHARS}]*|твар[{_WORD_CHARS}]*|козел[{_WORD_CHARS}]*|лох[{_WORD_CHARS}]*|чмо|падл[{_WORD_CHARS}]*)",
    rf"(?:fuck[{_WORD_CHARS}]*|shit[{_WORD_CHARS}]*|bitch[{_WORD_CHARS}]*|asshole[{_WORD_CHARS}]*|bastard[{_WORD_CHARS}]*|dick[{_WORD_CHARS}]*|cunt[{_WORD_CHARS}]*|whore[{_WORD_CHARS}]*|slut[{_WORD_CHARS}]*|motherfuck[{_WORD_CHARS}]*|idiot[{_WORD_CHARS}]*|moron[{_WORD_CHARS}]*|dumbass[{_WORD_CHARS}]*)",
]

_PROFANITY_RE = re.compile(
    rf"(?<![{_WORD_CHARS}])(?:{'|'.join(_TOKEN_PATTERNS)})(?![{_WORD_CHARS}])",
    re.IGNORECASE,
)


def _normalize(text: str) -> str:
    value = unicodedata.normalize("NFKC", text or "").lower().translate(_CHAR_MAP)
    value = re.sub(r"([a-zа-я])\1{2,}", r"\1\1", value)
    return value


def contains_profanity(text: str | None) -> bool:
    if not text:
        return False
    normalized = _normalize(text)
    spaced = re.sub(r"[^0-9a-zа-я]+", " ", normalized, flags=re.IGNORECASE)
    return bool(_PROFANITY_RE.search(spaced))


def ensure_clean_text(*values: str | None) -> None:
    if any(contains_profanity(value) for value in values):
        raise HTTPException(status_code=400, detail=PROFANITY_ERROR)
