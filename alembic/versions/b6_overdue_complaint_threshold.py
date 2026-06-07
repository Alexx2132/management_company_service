"""add overdue complaint threshold setting

Revision ID: b6_overdue_complaint_threshold
Revises: b5_disp_perms
Create Date: 2026-05-01 10:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b6_overdue_complaint_threshold"
down_revision: Union[str, Sequence[str], None] = "b5_disp_perms"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column("complaint_overdue_after_minutes", sa.Integer(), nullable=False, server_default="360"),
    )
    op.alter_column("app_settings", "complaint_overdue_after_minutes", server_default=None)


def downgrade() -> None:
    op.drop_column("app_settings", "complaint_overdue_after_minutes")
