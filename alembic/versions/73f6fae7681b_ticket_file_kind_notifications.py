"""ticket file kind + notifications

Revision ID: 73f6fae7681b
Revises: 6fc7e53f3e24
Create Date: 2026-02-13 18:50:23.696673

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '73f6fae7681b'
down_revision: Union[str, Sequence[str], None] = '6fc7e53f3e24'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # ---------------------------------------------------------------------
    # 0) PostgreSQL: ДОБАВЛЯЕМ НОВЫЕ ЗНАЧЕНИЯ В УЖЕ СУЩЕСТВУЮЩИЙ ENUM ticketstatus
    #    Alembic autogenerate это почти никогда не делает сам.
    #
    #    ВАЖНО: здесь значения в нижнем регистре, как в твоём Enum:
    #    not_confirmed, needs_reassign, complaint
    #
    #    Если твой тип называется НЕ "ticketstatus", выполни запрос:
    #    SELECT t.typname, e.enumlabel FROM pg_enum e JOIN pg_type t ON t.oid=e.enumtypid ORDER BY 1,2;
    # ---------------------------------------------------------------------
    op.execute("""
    DO $$
    BEGIN
        IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'ticketstatus') THEN

            IF NOT EXISTS (
                SELECT 1
                FROM pg_enum e
                JOIN pg_type t ON t.oid = e.enumtypid
                WHERE t.typname = 'ticketstatus' AND e.enumlabel = 'not_confirmed'
            ) THEN
                ALTER TYPE ticketstatus ADD VALUE 'not_confirmed';
            END IF;

            IF NOT EXISTS (
                SELECT 1
                FROM pg_enum e
                JOIN pg_type t ON t.oid = e.enumtypid
                WHERE t.typname = 'ticketstatus' AND e.enumlabel = 'needs_reassign'
            ) THEN
                ALTER TYPE ticketstatus ADD VALUE 'needs_reassign';
            END IF;

            IF NOT EXISTS (
                SELECT 1
                FROM pg_enum e
                JOIN pg_type t ON t.oid = e.enumtypid
                WHERE t.typname = 'ticketstatus' AND e.enumlabel = 'complaint'
            ) THEN
                ALTER TYPE ticketstatus ADD VALUE 'complaint';
            END IF;

        END IF;
    END $$;
    """)

    # ---------------------------------------------------------------------
    # 1) Таблицы жалоб (если у тебя их раньше не было)
    # ---------------------------------------------------------------------
    op.create_table(
        'ticket_complaints',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ticket_id', sa.Integer(), nullable=False),
        sa.Column('author_id', sa.Integer(), nullable=False),
        sa.Column('complaint_type', sa.Enum('OVERDUE', 'QUALITY', name='complainttype'), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.Enum('OPEN', 'RESOLVED', 'DISMISSED', name='complaintstatus'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('resolver_id', sa.Integer(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('resolution_comment', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['author_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['resolver_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ticket_complaints_id'), 'ticket_complaints', ['id'], unique=False)

    op.create_table(
        'complaint_files',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('complaint_id', sa.Integer(), nullable=False),
        sa.Column('file_path', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['complaint_id'], ['ticket_complaints.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_complaint_files_id'), 'complaint_files', ['id'], unique=False)

    # ---------------------------------------------------------------------
    # 2) Таблица notifications (лучше дать is_read дефолт false)
    # ---------------------------------------------------------------------
    op.create_table(
        'notifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('notif_type', sa.String(), nullable=False),
        sa.Column('ticket_id', sa.Integer(), nullable=True),
        sa.Column('complaint_id', sa.Integer(), nullable=True),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('read_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['complaint_id'], ['ticket_complaints.id'], ),
        sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_notifications_id'), 'notifications', ['id'], unique=False)
    op.create_index(op.f('ix_notifications_user_id'), 'notifications', ['user_id'], unique=False)

    # ------------------------------------
