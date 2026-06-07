"""add missing ticket_files.kind

Revision ID: d450d1c926f5
Revises: 73f6fae7681b
Create Date: 2026-02-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "d450d1c926f5"
down_revision: Union[str, Sequence[str], None] = "73f6fae7681b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) Создаём enum-тип ticketfilekind, если его нет
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'ticketfilekind') THEN
            CREATE TYPE ticketfilekind AS ENUM ('BEFORE', 'AFTER', 'LEGACY');
        END IF;
    END $$;
    """)

    # 2) Добавляем колонку kind, если её нет (с DEFAULT, чтобы не упасть на существующих строках)
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_name='ticket_files' AND column_name='kind'
        ) THEN
            ALTER TABLE ticket_files
            ADD COLUMN kind ticketfilekind NOT NULL DEFAULT 'LEGACY';
        END IF;
    END $$;
    """)

    # 3) (Опционально) убрать DEFAULT можно позже, но лучше оставить для совместимости
    # op.execute("ALTER TABLE ticket_files ALTER COLUMN kind DROP DEFAULT;")


def downgrade() -> None:
    op.execute("""
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_name='ticket_files' AND column_name='kind'
        ) THEN
            ALTER TABLE ticket_files DROP COLUMN kind;
        END IF;
    END $$;
    """)
