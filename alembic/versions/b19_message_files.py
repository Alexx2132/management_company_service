"""message file attachments

Revision ID: b19_message_files
Revises: b18_messages
Create Date: 2026-05-31
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b19_message_files"
down_revision: Union[str, Sequence[str], None] = "b18_messages"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "message_files",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=False),
        sa.Column("file_url", sa.String(length=500), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("content_type", sa.String(length=120), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_message_files_id"), "message_files", ["id"], unique=False)
    op.create_index(op.f("ix_message_files_message_id"), "message_files", ["message_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_message_files_message_id"), table_name="message_files")
    op.drop_index(op.f("ix_message_files_id"), table_name="message_files")
    op.drop_table("message_files")
