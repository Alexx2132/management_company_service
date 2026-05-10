import sys
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

sys.path.append(os.getcwd())

from app.core.config import settings
from app.db.base import Base

from app.models.user import User
from app.models.ticket import Ticket, TicketFile
from app.models.location import House
from app.models.announcement import Announcement
from app.models.category import Category
from app.models.history import TicketHistory
from app.models.ticket_complaint import TicketComplaint, ComplaintFile
from app.models.notification import Notification
from app.models.push_device_token import PushDeviceToken
from app.models.remark import Remark
from app.models.ticket_comment import TicketComment
from app.models.house_info import HouseEvent, EmergencyContact, HouseSchedule
from app.models.app_settings import AppSettings
from app.models.ticket_complaint import ComplaintComment

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
