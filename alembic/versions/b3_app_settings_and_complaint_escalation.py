"""app settings and complaint escalation

Revision ID: b3_app_settings_escalation
Revises: a2_2_executor_schedule_load
Create Date: 2026-04-26 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b3_app_settings_escalation"
down_revision: Union[str, Sequence[str], None] = "a2_2_executor_schedule_load"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("complaint_escalate_after_minutes", sa.Integer(), nullable=False, server_default="1440"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_app_settings_id"), "app_settings", ["id"], unique=False)

    op.execute("ALTER TYPE complainttype ADD VALUE IF NOT EXISTS 'DISPATCHER_INACTION'")

    op.add_column("ticket_complaints", sa.Column("parent_complaint_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_ticket_complaints_parent_complaint_id",
        "ticket_complaints",
        "ticket_complaints",
        ["parent_complaint_id"],
        ["id"],
    )

    op.create_table(
        "complaint_comments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("complaint_id", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["complaint_id"], ["ticket_complaints.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_complaint_comments_id"), "complaint_comments", ["id"], unique=False)
    op.create_index(op.f("ix_complaint_comments_complaint_id"), "complaint_comments", ["complaint_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_complaint_comments_complaint_id"), table_name="complaint_comments")
    op.drop_index(op.f("ix_complaint_comments_id"), table_name="complaint_comments")
    op.drop_table("complaint_comments")

    op.drop_constraint("fk_ticket_complaints_parent_complaint_id", "ticket_complaints", type_="foreignkey")
    op.drop_column("ticket_complaints", "parent_complaint_id")

    op.drop_index(op.f("ix_app_settings_id"), table_name="app_settings")
    op.drop_table("app_settings")
