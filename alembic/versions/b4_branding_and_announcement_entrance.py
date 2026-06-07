"""branding settings and announcement entrance targeting

Revision ID: b4_brand_ann_entrance
Revises: b3_app_settings_escalation
Create Date: 2026-04-26 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b4_brand_ann_entrance"
down_revision: Union[str, Sequence[str], None] = "b3_app_settings_escalation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column("app_brand", sa.String(length=120), nullable=False, server_default="UK WEB"),
    )
    op.add_column(
        "app_settings",
        sa.Column("login_title", sa.String(length=200), nullable=False, server_default="Вход в веб-версию"),
    )

    op.add_column("announcements", sa.Column("target_entrance_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_announcements_target_entrance_id",
        "announcements",
        "house_entrances",
        ["target_entrance_id"],
        ["id"],
    )

    op.alter_column("app_settings", "app_brand", server_default=None)
    op.alter_column("app_settings", "login_title", server_default=None)


def downgrade() -> None:
    op.drop_constraint("fk_announcements_target_entrance_id", "announcements", type_="foreignkey")
    op.drop_column("announcements", "target_entrance_id")

    op.drop_column("app_settings", "login_title")
    op.drop_column("app_settings", "app_brand")
