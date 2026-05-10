"""phase a2.2 executor schedule and load

Revision ID: a2_2_executor_schedule_load
Revises: REPLACE_WITH_CURRENT_HEAD
Create Date: 2026-04-17 19:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a2_2_executor_schedule_load"
down_revision: Union[str, Sequence[str], None] = "a2_1_executor_foundation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "executor_work_schedules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("executor_id", sa.Integer(), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("work_start", sa.Time(), nullable=False),
        sa.Column("work_end", sa.Time(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["executor_id"], ["executor_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("executor_id", "weekday", name="uq_executor_work_schedule_weekday")
    )
    op.create_index(op.f("ix_executor_work_schedules_id"), "executor_work_schedules", ["id"], unique=False)
    op.create_index(op.f("ix_executor_work_schedules_executor_id"), "executor_work_schedules", ["executor_id"], unique=False)

    op.create_table(
        "executor_days_off",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("executor_id", sa.Integer(), nullable=False),
        sa.Column("off_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["executor_id"], ["executor_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("executor_id", "off_date", name="uq_executor_day_off_date")
    )
    op.create_index(op.f("ix_executor_days_off_id"), "executor_days_off", ["id"], unique=False)
    op.create_index(op.f("ix_executor_days_off_executor_id"), "executor_days_off", ["executor_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_executor_days_off_executor_id"), table_name="executor_days_off")
    op.drop_index(op.f("ix_executor_days_off_id"), table_name="executor_days_off")
    op.drop_table("executor_days_off")

    op.drop_index(op.f("ix_executor_work_schedules_executor_id"), table_name="executor_work_schedules")
    op.drop_index(op.f("ix_executor_work_schedules_id"), table_name="executor_work_schedules")
    op.drop_table("executor_work_schedules")