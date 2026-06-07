"""user and announcement history

Revision ID: b20_user_announcement_history
Revises: b19_message_files
Create Date: 2026-06-01 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b20_user_announcement_history"
down_revision: Union[str, None] = "b19_message_files"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_change_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("field_name", sa.String(length=64), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_change_history_id"), "user_change_history", ["id"], unique=False)
    op.create_index(op.f("ix_user_change_history_user_id"), "user_change_history", ["user_id"], unique=False)
    op.create_index(op.f("ix_user_change_history_actor_id"), "user_change_history", ["actor_id"], unique=False)

    op.create_table(
        "announcement_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("announcement_id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["announcement_id"], ["announcements.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_announcement_history_id"), "announcement_history", ["id"], unique=False)
    op.create_index(op.f("ix_announcement_history_announcement_id"), "announcement_history", ["announcement_id"], unique=False)
    op.create_index(op.f("ix_announcement_history_actor_id"), "announcement_history", ["actor_id"], unique=False)
    op.execute(
        """
        INSERT INTO announcement_history (announcement_id, actor_id, action, new_value, created_at)
        SELECT id, author_id, 'created', 'Создано объявление', COALESCE(created_at, NOW())
        FROM announcements
        """
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_announcement_history_actor_id"), table_name="announcement_history")
    op.drop_index(op.f("ix_announcement_history_announcement_id"), table_name="announcement_history")
    op.drop_index(op.f("ix_announcement_history_id"), table_name="announcement_history")
    op.drop_table("announcement_history")
    op.drop_index(op.f("ix_user_change_history_actor_id"), table_name="user_change_history")
    op.drop_index(op.f("ix_user_change_history_user_id"), table_name="user_change_history")
    op.drop_index(op.f("ix_user_change_history_id"), table_name="user_change_history")
    op.drop_table("user_change_history")
