"""house info type dictionaries

Revision ID: b14_house_info_type_dictionaries
Revises: b13_admin_assistant_perms
Create Date: 2026-05-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b14_house_info_type_dictionaries"
down_revision: Union[str, Sequence[str], None] = "b13_admin_assistant_perms"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "house_info_types",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("type_group", sa.String(length=32), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("type_group", "code", name="uq_house_info_type_group_code"),
    )
    op.create_index(op.f("ix_house_info_types_id"), "house_info_types", ["id"], unique=False)
    op.create_index(op.f("ix_house_info_types_type_group"), "house_info_types", ["type_group"], unique=False)
    op.create_index(op.f("ix_house_info_types_code"), "house_info_types", ["code"], unique=False)

    op.execute(
        """
        INSERT INTO house_info_types (type_group, code, name, is_active)
        VALUES
            ('event', 'planned_work', 'Плановые работы', true),
            ('event', 'planned_outage', 'Плановое отключение', true),
            ('schedule', 'cleaning', 'Уборка', true),
            ('schedule', 'inspection', 'Проверка', true),
            ('schedule', 'maintenance', 'Обслуживание', true)
        ON CONFLICT (type_group, code) DO NOTHING
        """
    )

    op.alter_column(
        "house_events",
        "event_type",
        existing_type=sa.Enum("PLANNED_OUTAGE", "PLANNED_WORK", name="houseeventtype"),
        type_=sa.String(length=64),
        existing_nullable=False,
        postgresql_using="lower(event_type::text)",
    )
    op.alter_column(
        "house_schedules",
        "schedule_type",
        existing_type=sa.Enum("CLEANING", "INSPECTION", "MAINTENANCE", name="housescheduletype"),
        type_=sa.String(length=64),
        existing_nullable=False,
        postgresql_using="lower(schedule_type::text)",
    )

    op.execute("DROP TYPE IF EXISTS houseeventtype")
    op.execute("DROP TYPE IF EXISTS housescheduletype")


def downgrade() -> None:
    op.execute("CREATE TYPE houseeventtype AS ENUM ('PLANNED_OUTAGE', 'PLANNED_WORK')")
    op.execute("CREATE TYPE housescheduletype AS ENUM ('CLEANING', 'INSPECTION', 'MAINTENANCE')")

    op.execute(
        """
        UPDATE house_events
        SET event_type = CASE
            WHEN event_type = 'planned_outage' THEN 'PLANNED_OUTAGE'
            ELSE 'PLANNED_WORK'
        END
        """
    )
    op.execute(
        """
        UPDATE house_schedules
        SET schedule_type = CASE
            WHEN schedule_type = 'inspection' THEN 'INSPECTION'
            WHEN schedule_type = 'maintenance' THEN 'MAINTENANCE'
            ELSE 'CLEANING'
        END
        """
    )

    op.alter_column(
        "house_schedules",
        "schedule_type",
        existing_type=sa.String(length=64),
        type_=sa.Enum("CLEANING", "INSPECTION", "MAINTENANCE", name="housescheduletype"),
        existing_nullable=False,
        postgresql_using="schedule_type::housescheduletype",
    )
    op.alter_column(
        "house_events",
        "event_type",
        existing_type=sa.String(length=64),
        type_=sa.Enum("PLANNED_OUTAGE", "PLANNED_WORK", name="houseeventtype"),
        existing_nullable=False,
        postgresql_using="event_type::houseeventtype",
    )

    op.drop_index(op.f("ix_house_info_types_code"), table_name="house_info_types")
    op.drop_index(op.f("ix_house_info_types_type_group"), table_name="house_info_types")
    op.drop_index(op.f("ix_house_info_types_id"), table_name="house_info_types")
    op.drop_table("house_info_types")
