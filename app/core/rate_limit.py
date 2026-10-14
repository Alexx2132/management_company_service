import hashlib
import hmac
import math
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import case, delete
from sqlalchemy.dialects.postgresql import insert

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.auth_rate_limit import AuthRateLimit


async def consume_auth_attempt(scope: str, value: str, limit: int, seconds: int) -> None:
    # Не сохраняем логины и IP в таблице ограничений в открытом виде.
    key = hmac.new(settings.SECRET_KEY.encode(), f"{scope}:{value}".encode(), hashlib.sha256).hexdigest()
    now = datetime.now(timezone.utc)
    expires = now + timedelta(seconds=seconds)
    stale = AuthRateLimit.expires_at <= now
    statement = insert(AuthRateLimit).values(key=key, attempts=1, expires_at=expires)
    statement = statement.on_conflict_do_update(index_elements=[AuthRateLimit.key], set_={
        "attempts": case((stale, 1), else_=AuthRateLimit.attempts + 1),
        "expires_at": case((stale, expires), else_=AuthRateLimit.expires_at),
    }).returning(AuthRateLimit.attempts, AuthRateLimit.expires_at)
    async with SessionLocal() as db:
        await db.execute(delete(AuthRateLimit).where(AuthRateLimit.expires_at <= now))
        attempts, reset_at = (await db.execute(statement)).one()
        await db.commit()
    if attempts > limit:
        retry_after = max(1, math.ceil((reset_at - now).total_seconds()))
        raise HTTPException(status_code=429, detail="Слишком много попыток. Попробуйте позже.",
                            headers={"Retry-After": str(retry_after)})
