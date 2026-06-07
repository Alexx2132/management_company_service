import os
import shutil
import uuid

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.file_upload import validate_image_upload
from app.core.profanity import ensure_clean_text
from app.models.app_settings import AppSettings
from app.models.user import User, UserRole
from app.schemas.app_settings import AppSettingsUpdate
from app.services.permissions import can_manage_service_settings


class AppSettingsService:
    DEFAULT_COMPLAINT_ESCALATION_MINUTES = 360
    MIN_COMPLAINT_ESCALATION_MINUTES = 1
    MAX_COMPLAINT_ESCALATION_MINUTES = 360
    DEFAULT_COMPLAINT_OVERDUE_MINUTES = 360
    MIN_COMPLAINT_OVERDUE_MINUTES = 1
    MAX_COMPLAINT_OVERDUE_MINUTES = 360
    DEFAULT_COMPLAINT_PRIMARY_LIMIT = 2
    MIN_COMPLAINT_PRIMARY_LIMIT = 1
    MAX_COMPLAINT_PRIMARY_LIMIT = 10
    LOGIN_BACKGROUND_DIR = os.path.join("static", "uploads", "settings")
    DEFAULT_APP_BRAND = "UK WEB"
    DEFAULT_LOGIN_TITLE = "Вход в веб-версию"
    DEFAULT_MOBILE_LOGIN_BRAND = "Управляющая компания"
    DEFAULT_MOBILE_LOGIN_TITLE = "Вход в систему"
    DEFAULT_MOBILE_LOGIN_SUBTITLE = "Жители отслеживают заявки, сотрудники контролируют их исполнение."
    DEFAULT_SERVICE_RULES_TEXT = (
        "Пользуйтесь сервисом добросовестно: не дублируйте заявки, указывайте достоверную информацию "
        "и соблюдайте уважительный тон в общении."
    )

    def __init__(self, db: Session):
        self.db = db

    def get_settings(self) -> AppSettings:
        settings = self.db.query(AppSettings).order_by(AppSettings.id.asc()).first()
        if settings:
            changed = False
            normalized_escalation = max(
                self.MIN_COMPLAINT_ESCALATION_MINUTES,
                min(int(settings.complaint_escalate_after_minutes or self.DEFAULT_COMPLAINT_ESCALATION_MINUTES), self.MAX_COMPLAINT_ESCALATION_MINUTES),
            )
            normalized_overdue = max(
                self.MIN_COMPLAINT_OVERDUE_MINUTES,
                min(int(settings.complaint_overdue_after_minutes or self.DEFAULT_COMPLAINT_OVERDUE_MINUTES), self.MAX_COMPLAINT_OVERDUE_MINUTES),
            )
            normalized_primary_limit = max(
                self.MIN_COMPLAINT_PRIMARY_LIMIT,
                min(int(getattr(settings, "complaint_primary_limit", None) or self.DEFAULT_COMPLAINT_PRIMARY_LIMIT), self.MAX_COMPLAINT_PRIMARY_LIMIT),
            )
            if settings.complaint_escalate_after_minutes != normalized_escalation:
                settings.complaint_escalate_after_minutes = normalized_escalation
                changed = True
            if settings.complaint_overdue_after_minutes != normalized_overdue:
                settings.complaint_overdue_after_minutes = normalized_overdue
                changed = True
            if getattr(settings, "complaint_primary_limit", None) != normalized_primary_limit:
                settings.complaint_primary_limit = normalized_primary_limit
                changed = True
            if not getattr(settings, "mobile_login_brand", None):
                settings.mobile_login_brand = self.DEFAULT_MOBILE_LOGIN_BRAND
                changed = True
            if not getattr(settings, "mobile_login_title", None):
                settings.mobile_login_title = self.DEFAULT_MOBILE_LOGIN_TITLE
                changed = True
            if not getattr(settings, "mobile_login_subtitle", None):
                settings.mobile_login_subtitle = self.DEFAULT_MOBILE_LOGIN_SUBTITLE
                changed = True
            if not getattr(settings, "service_rules_text", None):
                settings.service_rules_text = self.DEFAULT_SERVICE_RULES_TEXT
                changed = True
            if changed:
                self.db.commit()
                self.db.refresh(settings)
            return settings

        settings = AppSettings(
            complaint_escalate_after_minutes=self.DEFAULT_COMPLAINT_ESCALATION_MINUTES,
            complaint_overdue_after_minutes=self.DEFAULT_COMPLAINT_OVERDUE_MINUTES,
            complaint_primary_limit=self.DEFAULT_COMPLAINT_PRIMARY_LIMIT,
            app_brand=self.DEFAULT_APP_BRAND,
            login_title=self.DEFAULT_LOGIN_TITLE,
            mobile_login_brand=self.DEFAULT_MOBILE_LOGIN_BRAND,
            mobile_login_title=self.DEFAULT_MOBILE_LOGIN_TITLE,
            mobile_login_subtitle=self.DEFAULT_MOBILE_LOGIN_SUBTITLE,
            service_rules_text=self.DEFAULT_SERVICE_RULES_TEXT,
        )
        self.db.add(settings)
        self.db.commit()
        self.db.refresh(settings)
        return settings

    def _ensure_can_manage_branding(self, current_user: User) -> None:
        if not can_manage_service_settings(current_user):
            raise HTTPException(status_code=403, detail="Только администратор может менять оформление входа")

    def _delete_static_file(self, relative_path: str | None) -> None:
        if not relative_path or not relative_path.startswith("/static/uploads/settings/"):
            return

        disk_path = relative_path.lstrip("/").replace("/", os.sep)
        if os.path.exists(disk_path):
            os.remove(disk_path)

    def upload_login_background(self, file: UploadFile, current_user: User) -> AppSettings:
        self._ensure_can_manage_branding(current_user)
        ext, _ = validate_image_upload(file, max_size_mb=8)
        settings = self.get_settings()

        os.makedirs(self.LOGIN_BACKGROUND_DIR, exist_ok=True)
        filename = f"login-background-{uuid.uuid4().hex}.{ext}"
        disk_path = os.path.join(self.LOGIN_BACKGROUND_DIR, filename)

        file.file.seek(0)
        with open(disk_path, "wb") as output:
            shutil.copyfileobj(file.file, output)

        self._delete_static_file(settings.login_background_image)
        settings.login_background_image = f"/static/uploads/settings/{filename}"
        self.db.commit()
        self.db.refresh(settings)
        return settings

    def clear_login_background(self, current_user: User) -> AppSettings:
        self._ensure_can_manage_branding(current_user)
        settings = self.get_settings()
        self._delete_static_file(settings.login_background_image)
        settings.login_background_image = None
        self.db.commit()
        self.db.refresh(settings)
        return settings

    def update_settings(self, data: AppSettingsUpdate, current_user: User) -> AppSettings:
        can_manage_branding = can_manage_service_settings(current_user)
        can_manage_escalation = can_manage_service_settings(current_user)
        can_manage_overdue = current_user.role in [UserRole.ADMIN, UserRole.AUDITOR]
        can_manage_primary_limit = current_user.role in [UserRole.ADMIN, UserRole.AUDITOR]

        if not (can_manage_branding or can_manage_overdue or can_manage_primary_limit):
            raise HTTPException(status_code=403, detail="Настройки может изменять только администратор или аудитор")

        settings = self.get_settings()
        if data.complaint_escalate_after_minutes is not None:
            if not can_manage_escalation:
                raise HTTPException(status_code=403, detail="Только администратор может менять порог обращения в контролирующий орган")
            minutes = int(data.complaint_escalate_after_minutes)
            if minutes < self.MIN_COMPLAINT_ESCALATION_MINUTES or minutes > self.MAX_COMPLAINT_ESCALATION_MINUTES:
                raise HTTPException(
                    status_code=400,
                    detail="Порог обращения в контролирующий орган должен быть от 1 минуты до 6 часов",
                )
            settings.complaint_escalate_after_minutes = minutes
        if data.complaint_overdue_after_minutes is not None:
            if not can_manage_overdue:
                raise HTTPException(status_code=403, detail="Только аудитор или администратор может менять порог жалобы на отсутствие реакции")
            minutes = int(data.complaint_overdue_after_minutes)
            if minutes < self.MIN_COMPLAINT_OVERDUE_MINUTES or minutes > self.MAX_COMPLAINT_OVERDUE_MINUTES:
                raise HTTPException(
                    status_code=400,
                    detail="Порог жалобы на отсутствие реакции должен быть от 1 минуты до 6 часов",
            )
            settings.complaint_overdue_after_minutes = minutes
        if data.complaint_primary_limit is not None:
            if not can_manage_primary_limit:
                raise HTTPException(status_code=403, detail="Только аудитор или администратор может менять лимит жалоб")
            limit = int(data.complaint_primary_limit)
            if limit < self.MIN_COMPLAINT_PRIMARY_LIMIT or limit > self.MAX_COMPLAINT_PRIMARY_LIMIT:
                raise HTTPException(
                    status_code=400,
                    detail="Лимит обычных жалоб по заявке должен быть от 1 до 10",
                )
            settings.complaint_primary_limit = limit
        if data.app_brand is not None:
            if not can_manage_branding:
                raise HTTPException(status_code=403, detail="Только администратор может менять брендирование")
            settings.app_brand = data.app_brand.strip()
        if data.login_title is not None:
            if not can_manage_branding:
                raise HTTPException(status_code=403, detail="Только администратор может менять заголовок входа")
            settings.login_title = data.login_title.strip()
        if data.mobile_login_brand is not None:
            if not can_manage_branding:
                raise HTTPException(status_code=403, detail="Только администратор может менять мобильный экран входа")
            settings.mobile_login_brand = data.mobile_login_brand.strip()
        if data.mobile_login_title is not None:
            if not can_manage_branding:
                raise HTTPException(status_code=403, detail="Только администратор может менять мобильный экран входа")
            settings.mobile_login_title = data.mobile_login_title.strip()
        if data.mobile_login_subtitle is not None:
            if not can_manage_branding:
                raise HTTPException(status_code=403, detail="Только администратор может менять мобильный экран входа")
            ensure_clean_text(data.mobile_login_subtitle)
            settings.mobile_login_subtitle = data.mobile_login_subtitle.strip()
        if data.service_rules_text is not None:
            if not can_manage_branding:
                raise HTTPException(status_code=403, detail="Только администратор может менять правила сервиса")
            ensure_clean_text(data.service_rules_text)
            settings.service_rules_text = data.service_rules_text.strip()
        self.db.commit()
        self.db.refresh(settings)
        return settings
