"""login background and dispatcher ticket priorities

Revision ID: b16_login_bg_dispatcher_priority
Revises: b15_user_ban_reason
Create Date: 2026-05-25
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b16_login_bg_dispatcher_priority"
down_revision: Union[str, Sequence[str], None] = "b15_user_ban_reason"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("app_settings", sa.Column("login_background_image", sa.String(length=500), nullable=True))
    op.add_column("users", sa.Column("allowed_ticket_priorities", sa.String(length=120), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "allowed_ticket_priorities")
    op.drop_column("app_settings", "login_background_image")
