import asyncio
import logging
import os
from datetime import datetime
from typing import Iterable
from threading import Lock

from sqlalchemy.orm import Session
from sqlalchemy import update

from app.models.push_device_token import PushDeviceToken

logger = logging.getLogger(__name__)
_delivery_tasks: set[asyncio.Task] = set()
_firebase_lock = Lock()


def schedule_push_deliveries(deliveries: list) -> None:
    for tokens, payload in deliveries:
        task = asyncio.create_task(PushNotificationService._deliver_async(tokens, payload))
        _delivery_tasks.add(task)
        task.add_done_callback(_delivery_tasks.discard)


async def finish_push_deliveries() -> None:
    if _delivery_tasks:
        try:
            await asyncio.wait_for(asyncio.gather(*list(_delivery_tasks), return_exceptions=True), timeout=15)
        except TimeoutError:
            logger.warning("Pending push delivery timed out during shutdown")


class PushNotificationService:
    def __init__(self, db: Session):
        self.db = db

    def register_token(
        self,
        user,
        token: str,
        platform: str = "android",
        device_name: str | None = None,
    ) -> PushDeviceToken:
        normalized_token = (token or "").strip()
        if not normalized_token:
            raise ValueError("Push token is required")

        now = datetime.utcnow()
        role = user.role.value if hasattr(user.role, "value") else str(user.role)
        platform_value = (platform or "android").strip().lower()[:32] or "android"
        device_value = (device_name or "").strip()[:160] or None

        obj = self.db.query(PushDeviceToken).filter(PushDeviceToken.token == normalized_token).first()
        if obj is None:
            obj = PushDeviceToken(
                user_id=user.id,
                token=normalized_token[:512],
                platform=platform_value,
                role=role,
                device_name=device_value,
                is_active=True,
                last_seen_at=now,
                created_at=now,
                updated_at=now,
            )
            self.db.add(obj)
        else:
            obj.user_id = user.id
            obj.platform = platform_value
            obj.role = role
            obj.device_name = device_value
            obj.is_active = True
            obj.last_seen_at = now
            obj.updated_at = now

        self.db.commit()
        self.db.refresh(obj)
        return obj

    def deactivate_token(self, user, token: str) -> bool:
        normalized_token = (token or "").strip()
        if not normalized_token:
            return False

        obj = (
            self.db.query(PushDeviceToken)
            .filter(PushDeviceToken.token == normalized_token, PushDeviceToken.user_id == user.id)
            .first()
        )
        if obj is None:
            return False

        obj.is_active = False
        obj.updated_at = datetime.utcnow()
        self.db.commit()
        return True

    def send_to_users(
        self,
        user_ids: Iterable[int],
        title: str,
        message: str,
        data: dict | None = None,
    ) -> None:
        target_ids = {int(user_id) for user_id in user_ids if user_id is not None}
        if not target_ids:
            return

        tokens = (
            self.db.query(PushDeviceToken)
            .filter(PushDeviceToken.user_id.in_(target_ids), PushDeviceToken.is_active.is_(True))
            .all()
        )
        if not tokens:
            return

        payload_data = {
            key: str(value)
            for key, value in (data or {}).items()
            if value is not None and str(value) != ""
        }
        payload_data.setdefault("title", title or "")
        payload_data.setdefault("message", message or "")

        token_data = [(obj.id, obj.token, obj.user_id) for obj in tokens]
        if self.db.get_bind().dialect.is_async:
            self.db.info.setdefault("pending_push_deliveries", []).append((token_data, payload_data))
            return
        invalid_ids = self._send_payload(token_data, payload_data)
        if invalid_ids:
            self.db.query(PushDeviceToken).filter(PushDeviceToken.id.in_(invalid_ids)).update(
                {PushDeviceToken.is_active: False, PushDeviceToken.updated_at: datetime.utcnow()},
                synchronize_session=False,
            )
            self.db.commit()

    @staticmethod
    def _send_payload(tokens: list[tuple[int, str, int]], payload_data: dict) -> list[int]:
        with _firebase_lock:
            messaging = PushNotificationService._get_firebase_messaging()
        if messaging is None:
            return []
        invalid_ids = []
        for token_id, token, user_id in tokens:
            try:
                firebase_message = messaging.Message(
                    token=token,
                    data={**payload_data, "recipient_user_id": str(user_id)},
                    android=messaging.AndroidConfig(
                        priority="high",
                    ),
                )
                messaging.send(firebase_message)
            except Exception as exc:
                if PushNotificationService._looks_like_invalid_token(exc):
                    invalid_ids.append(token_id)
                logger.warning("FCM push delivery failed: %s", exc)

        return invalid_ids

    @staticmethod
    async def _deliver_async(tokens: list[tuple[int, str, int]], payload: dict) -> None:
        from app.db.session import SessionLocal

        try:
            invalid_ids = await asyncio.to_thread(PushNotificationService._send_payload, tokens, payload)
            if invalid_ids:
                async with SessionLocal() as db:
                    await db.execute(
                        update(PushDeviceToken).where(PushDeviceToken.id.in_(invalid_ids)).values(
                            is_active=False, updated_at=datetime.utcnow(),
                        )
                    )
                    await db.commit()
        except Exception:
            logger.exception("Background push delivery failed")

    @staticmethod
    def _looks_like_invalid_token(exc: Exception) -> bool:
        text = str(exc).lower()
        return any(
            marker in text
            for marker in (
                "registration-token-not-registered",
                "invalid-registration-token",
                "requested entity was not found",
                "sender id mismatch",
            )
        )

    @staticmethod
    def _get_firebase_messaging():
        from app.core.config import settings

        service_account_file = (
            settings.FCM_SERVICE_ACCOUNT_FILE
            or os.getenv("FCM_SERVICE_ACCOUNT_FILE")
            or os.getenv("FIREBASE_SERVICE_ACCOUNT_FILE")
            or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        )
        if not service_account_file or not os.path.exists(service_account_file):
            return None

        try:
            import firebase_admin
            from firebase_admin import credentials, messaging
        except Exception as exc:
            logger.warning("firebase-admin is not available, push notifications are skipped: %s", exc)
            return None

        try:
            if not firebase_admin._apps:
                cred = credentials.Certificate(service_account_file)
                firebase_admin.initialize_app(cred, options={"httpTimeout": 10})
            return messaging
        except Exception as exc:
            logger.warning("Firebase initialization failed, push notifications are skipped: %s", exc)
            return None
