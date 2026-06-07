"""notification context fields

Revision ID: b17_notification_context
Revises: b16_login_bg_dispatcher_priority
Create Date: 2026-05-28
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b17_notification_context"
down_revision: Union[str, Sequence[str], None] = "b16_login_bg_dispatcher_priority"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("notifications", sa.Column("ban_conversation_id", sa.Integer(), nullable=True))
    op.create_index(
        "ix_notifications_ban_conversation_id",
        "notifications",
        ["ban_conversation_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_notifications_ban_conversation_id",
        "notifications",
        "ban_conversations",
        ["ban_conversation_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_notifications_ban_conversation_id", "notifications", type_="foreignkey")
    op.drop_index("ix_notifications_ban_conversation_id", table_name="notifications")
    op.drop_column("notifications", "ban_conversation_id")
