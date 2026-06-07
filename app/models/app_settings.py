from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.db.base import Base


class AppSettings(Base):
    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True, index=True)
    complaint_escalate_after_minutes = Column(Integer, nullable=False, default=360)
    complaint_overdue_after_minutes = Column(Integer, nullable=False, default=360)
    complaint_primary_limit = Column(Integer, nullable=False, default=2)
    app_brand = Column(String(120), nullable=False, default="UK WEB")
    login_title = Column(String(200), nullable=False, default="Вход в веб-версию")
    mobile_login_brand = Column(String(120), nullable=False, default="Управляющая компания")
    mobile_login_title = Column(String(200), nullable=False, default="Вход в систему")
    mobile_login_subtitle = Column(String(300), nullable=False, default="Жители отслеживают заявки, сотрудники контролируют их исполнение.")
    login_background_image = Column(String(500), nullable=True)
    service_rules_text = Column(
        Text,
        nullable=False,
        default="Пользуйтесь сервисом добросовестно: не дублируйте заявки, указывайте достоверную информацию и соблюдайте уважительный тон в общении.",
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
