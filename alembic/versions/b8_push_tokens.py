"""push device tokens

Revision ID: b8_push_tokens
Revises: b7_complaint_limit
Create Date: 2026-05-06 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b8_push_tokens"
down_revision: Union[str, Sequence[str], None] = "b7_complaint_limit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "push_device_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(length=512), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False, server_default="android"),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("device_name", sa.String(length=160), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_push_device_tokens_id"), "push_device_tokens", ["id"], unique=False)
    op.create_index(op.f("ix_push_device_tokens_is_active"), "push_device_tokens", ["is_active"], unique=False)
    op.create_index(op.f("ix_push_device_tokens_role"), "push_device_tokens", ["role"], unique=False)
    op.create_index(op.f("ix_push_device_tokens_token"), "push_device_tokens", ["token"], unique=True)
    op.create_index(op.f("ix_push_device_tokens_user_id"), "push_device_tokens", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_push_device_tokens_user_id"), table_name="push_device_tokens")
    op.drop_index(op.f("ix_push_device_tokens_token"), table_name="push_device_tokens")
    op.drop_index(op.f("ix_push_device_tokens_role"), table_name="push_device_tokens")
    op.drop_index(op.f("ix_push_device_tokens_is_active"), table_name="push_device_tokens")
    op.drop_index(op.f("ix_push_device_tokens_id"), table_name="push_device_tokens")
    op.drop_table("push_device_tokens")
