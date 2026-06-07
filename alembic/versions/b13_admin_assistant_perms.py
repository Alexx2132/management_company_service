"""admin assistant permissions and announcement links

Revision ID: b13_admin_assistant_perms
Revises: b12_external_tickets_ban_appeals
Create Date: 2026-05-10
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b13_admin_assistant_perms"
down_revision: Union[str, Sequence[str], None] = "b12_external_tickets_ban_appeals"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'ADMIN_ASSISTANT'")

    for column_name in (
        "can_create_users",
        "can_manage_executor_schedules",
        "can_manage_service_settings",
        "can_manage_remarks",
        "can_manage_house_info",
        "can_manage_announcements",
    ):
        op.add_column(
            "users",
            sa.Column(column_name, sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        op.alter_column("users", column_name, server_default=None)

    op.add_column("notifications", sa.Column("announcement_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_notifications_announcement_id_announcements",
        "notifications",
        "announcements",
        ["announcement_id"],
        ["id"],
    )

    op.add_column("house_schedules", sa.Column("start_time", sa.String(length=8), nullable=True))
    op.add_column("house_schedules", sa.Column("end_time", sa.String(length=8), nullable=True))


def downgrade() -> None:
    op.drop_column("house_schedules", "end_time")
    op.drop_column("house_schedules", "start_time")

    op.drop_constraint("fk_notifications_announcement_id_announcements", "notifications", type_="foreignkey")
    op.drop_column("notifications", "announcement_id")

    for column_name in (
        "can_manage_announcements",
        "can_manage_house_info",
        "can_manage_remarks",
        "can_manage_service_settings",
        "can_manage_executor_schedules",
        "can_create_users",
    ):
        op.drop_column("users", column_name)
