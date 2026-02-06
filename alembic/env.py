import sys
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# ------------------------------------------------------------------
# 1. Добавляем путь к приложению, чтобы Alembic видел папку 'app'
# ------------------------------------------------------------------
sys.path.append(os.getcwd())

# 2. Импортируем наши настройки и Base
from app.core.config import settings
from app.db.base import Base

# 3. ВАЖНО: Импортируем ВСЕ модели.
# Если их не импортировать, Alembic подумает, что база пустая!
from app.models.user import User
from app.models.ticket import Ticket
# from app.models.location import House (когда создадите)

# ------------------------------------------------------------------

# Config object, which provides access to the values within the .ini file in use.
config = context.config

# 4. Подменяем URL подключения на тот, что в settings (.env)
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 5. Указываем метаданные для autogenerate
target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.
    (Генерация SQL скрипта без подключения к БД)
    """
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
    """Run migrations in 'online' mode.
    (Реальное подключение к БД и выполнение миграций)
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
