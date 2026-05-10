"""mobile login settings

Revision ID: b11_mobile_login_settings
Revises: b10_category_types_ticket_place
Create Date: 2026-05-09
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b11_mobile_login_settings"
down_revision: Union[str, Sequence[str], None] = "b10_category_types_ticket_place"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column("mobile_login_brand", sa.String(length=120), nullable=False, server_default="Управляющая компания"),
    )
    op.add_column(
        "app_settings",
        sa.Column("mobile_login_title", sa.String(length=200), nullable=False, server_default="Вход в систему"),
    )
    op.add_column(
        "app_settings",
        sa.Column(
            "mobile_login_subtitle",
            sa.String(length=300),
            nullable=False,
            server_default="Жители отслеживают заявки, сотрудники контролируют их исполнение.",
        ),
    )
    op.alter_column("app_settings", "mobile_login_brand", server_default=None)
    op.alter_column("app_settings", "mobile_login_title", server_default=None)
    op.alter_column("app_settings", "mobile_login_subtitle", server_default=None)


def downgrade() -> None:
    op.drop_column("app_settings", "mobile_login_subtitle")
    op.drop_column("app_settings", "mobile_login_title")
    op.drop_column("app_settings", "mobile_login_brand")
