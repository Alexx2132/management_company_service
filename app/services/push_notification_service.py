import logging
import os
from datetime import datetime
from typing import Iterable

from sqlalchemy.orm import Session

from app.models.push_device_token import PushDeviceToken

logger = logging.getLogger(__name__)


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

        messaging = self._get_firebase_messaging()
        if messaging is None:
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

        dirty = False
        for token_obj in tokens:
            try:
                firebase_message = messaging.Message(
                    token=token_obj.token,
                    data=payload_data,
                    android=messaging.AndroidConfig(
                        priority="high",
                    ),
                )
                messaging.send(firebase_message)
            except Exception as exc:  # pragma: no cover - depends on external FCM state
                if self._looks_like_invalid_token(exc):
                    token_obj.is_active = False
                    token_obj.updated_at = datetime.utcnow()
                    dirty = True
                logger.warning("FCM push delivery failed: %s", exc)

        if dirty:
            self.db.commit()

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
        except Exception as exc:  # pragma: no cover - optional dependency guard
            logger.warning("firebase-admin is not available, push notifications are skipped: %s", exc)
            return None

        try:
            if not firebase_admin._apps:
                cred = credentials.Certificate(service_account_file)
                firebase_admin.initialize_app(cred)
            return messaging
        except Exception as exc:  # pragma: no cover - depends on service account file
            logger.warning("Firebase initialization failed, push notifications are skipped: %s", exc)
            return None
