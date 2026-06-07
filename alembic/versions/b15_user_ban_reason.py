"""user ban reason

Revision ID: b15_user_ban_reason
Revises: b14_house_info_type_dictionaries
Create Date: 2026-05-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b15_user_ban_reason"
down_revision: Union[str, Sequence[str], None] = "b14_house_info_type_dictionaries"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("ban_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "ban_reason")
