"""phase2 sla priorities reopen complaints

Revision ID: 616f9835768c
Revises: 3e032eb86786
Create Date: 2026-03-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "616f9835768c"
down_revision: Union[str, Sequence[str], None] = "3e032eb86786"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ticketpriority = sa.Enum(
    "LOW",
    "NORMAL",
    "HIGH",
    "EMERGENCY",
    name="ticketpriority"
)


def upgrade() -> None:
    """Upgrade schema."""

    # Сначала создаём enum-тип в PostgreSQL
    ticketpriority.create(op.get_bind(), checkfirst=True)

    # Потом добавляем колонку с временным server_default,
    # потому что таблица tickets уже не пустая
    op.add_column(
        "tickets",
        sa.Column(
            "priority",
            sa.Enum("LOW", "NORMAL", "HIGH", "EMERGENCY", name="ticketpriority"),
            nullable=False,
            server_default="NORMAL",
        ),
    )

    op.add_column("tickets", sa.Column("first_response_due_at", sa.DateTime(), nullable=True))
    op.add_column("tickets", sa.Column("due_at", sa.DateTime(), nullable=True))
    op.add_column("tickets", sa.Column("planned_visit_at", sa.DateTime(), nullable=True))
    op.add_column("tickets", sa.Column("assigned_at", sa.DateTime(), nullable=True))
    op.add_column("tickets", sa.Column("started_at", sa.DateTime(), nullable=True))
    op.add_column("tickets", sa.Column("done_at", sa.DateTime(), nullable=True))
    op.add_column("tickets", sa.Column("closed_at", sa.DateTime(), nullable=True))
    op.add_column("tickets", sa.Column("canceled_at", sa.DateTime(), nullable=True))
    op.add_column(
        "tickets",
        sa.Column("reopened_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("tickets", sa.Column("last_reopened_at", sa.DateTime(), nullable=True))

    # Заполняем существующие записи
    op.execute(
        """
        UPDATE tickets
        SET
            priority = COALESCE(priority, 'NORMAL'),
            first_response_due_at = COALESCE(first_response_due_at, created_at + interval '4 hour'),
            due_at = COALESCE(due_at, created_at + interval '72 hour'),
            assigned_at = CASE
                WHEN status IN ('ASSIGNED', 'IN_PROGRESS', 'DONE', 'CLOSED')
                THEN COALESCE(assigned_at, updated_at, created_at)
                ELSE assigned_at
            END,
            started_at = CASE
                WHEN status IN ('IN_PROGRESS', 'DONE', 'CLOSED')
                THEN COALESCE(started_at, updated_at, created_at)
                ELSE started_at
            END,
            done_at = CASE
                WHEN status IN ('DONE', 'CLOSED')
                THEN COALESCE(done_at, updated_at, created_at)
                ELSE done_at
            END,
            closed_at = CASE
                WHEN status = 'CLOSED'
                THEN COALESCE(closed_at, updated_at, created_at)
                ELSE closed_at
            END,
            canceled_at = CASE
                WHEN status = 'CANCELED'
                THEN COALESCE(canceled_at, updated_at, created_at)
                ELSE canceled_at
            END,
            reopened_count = COALESCE(reopened_count, 0)
        """
    )

    # Убираем временные дефолты
    op.alter_column("tickets", "priority", server_default=None)
    op.alter_column("tickets", "reopened_count", server_default=None)


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_column("tickets", "last_reopened_at")
    op.drop_column("tickets", "reopened_count")
    op.drop_column("tickets", "canceled_at")
    op.drop_column("tickets", "closed_at")
    op.drop_column("tickets", "done_at")
    op.drop_column("tickets", "started_at")
    op.drop_column("tickets", "assigned_at")
    op.drop_column("tickets", "planned_visit_at")
    op.drop_column("tickets", "due_at")
    op.drop_column("tickets", "first_response_due_at")
    op.drop_column("tickets", "priority")

    ticketpriority.drop(op.get_bind(), checkfirst=True)