"""dispatcher permissions

Revision ID: b5_disp_perms
Revises: b4_brand_ann_entrance
Create Date: 2026-04-26 21:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b5_disp_perms"
down_revision: Union[str, Sequence[str], None] = "b4_brand_ann_entrance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("can_manage_houses", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "users",
        sa.Column("can_ban_residents", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.alter_column("users", "can_manage_houses", server_default=None)
    op.alter_column("users", "can_ban_residents", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "can_ban_residents")
    op.drop_column("users", "can_manage_houses")
