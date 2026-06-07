"""add primary complaint limit setting

Revision ID: b7_complaint_limit
Revises: b6_overdue_complaint_threshold
Create Date: 2026-05-03 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7_complaint_limit"
down_revision: Union[str, Sequence[str], None] = "b6_overdue_complaint_threshold"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column("complaint_primary_limit", sa.Integer(), nullable=False, server_default="2"),
    )
    op.alter_column("app_settings", "complaint_primary_limit", server_default=None)


def downgrade() -> None:
    op.drop_column("app_settings", "complaint_primary_limit")
