"""general user messages

Revision ID: b18_messages
Revises: b17_notification_context
Create Date: 2026-05-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b18_messages"
down_revision: Union[str, Sequence[str], None] = "b17_notification_context"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "message_conversations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=220), nullable=True),
        sa.Column("context_type", sa.String(length=32), nullable=False),
        sa.Column("direct_key", sa.String(length=80), nullable=True),
        sa.Column("ticket_id", sa.Integer(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("is_closed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("direct_key"),
    )
    op.create_index(op.f("ix_message_conversations_id"), "message_conversations", ["id"], unique=False)
    op.create_index(op.f("ix_message_conversations_direct_key"), "message_conversations", ["direct_key"], unique=False)
    op.create_index(op.f("ix_message_conversations_ticket_id"), "message_conversations", ["ticket_id"], unique=False)
    op.create_index(op.f("ix_message_conversations_created_by_id"), "message_conversations", ["created_by_id"], unique=False)

    op.create_table(
        "message_participants",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("muted_until", sa.DateTime(), nullable=True),
        sa.Column("last_read_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["message_conversations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("conversation_id", "user_id", name="uq_message_participant"),
    )
    op.create_index(op.f("ix_message_participants_id"), "message_participants", ["id"], unique=False)
    op.create_index(op.f("ix_message_participants_conversation_id"), "message_participants", ["conversation_id"], unique=False)
    op.create_index(op.f("ix_message_participants_user_id"), "message_participants", ["user_id"], unique=False)

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("sender_id", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["message_conversations.id"]),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_messages_id"), "messages", ["id"], unique=False)
    op.create_index(op.f("ix_messages_conversation_id"), "messages", ["conversation_id"], unique=False)
    op.create_index(op.f("ix_messages_sender_id"), "messages", ["sender_id"], unique=False)

    op.add_column("notifications", sa.Column("message_conversation_id", sa.Integer(), nullable=True))
    op.create_index(
        "ix_notifications_message_conversation_id",
        "notifications",
        ["message_conversation_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_notifications_message_conversation_id",
        "notifications",
        "message_conversations",
        ["message_conversation_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_notifications_message_conversation_id", "notifications", type_="foreignkey")
    op.drop_index("ix_notifications_message_conversation_id", table_name="notifications")
    op.drop_column("notifications", "message_conversation_id")
    op.drop_index(op.f("ix_messages_sender_id"), table_name="messages")
    op.drop_index(op.f("ix_messages_conversation_id"), table_name="messages")
    op.drop_index(op.f("ix_messages_id"), table_name="messages")
    op.drop_table("messages")
    op.drop_index(op.f("ix_message_participants_user_id"), table_name="message_participants")
    op.drop_index(op.f("ix_message_participants_conversation_id"), table_name="message_participants")
    op.drop_index(op.f("ix_message_participants_id"), table_name="message_participants")
    op.drop_table("message_participants")
    op.drop_index(op.f("ix_message_conversations_created_by_id"), table_name="message_conversations")
    op.drop_index(op.f("ix_message_conversations_ticket_id"), table_name="message_conversations")
    op.drop_index(op.f("ix_message_conversations_direct_key"), table_name="message_conversations")
    op.drop_index(op.f("ix_message_conversations_id"), table_name="message_conversations")
    op.drop_table("message_conversations")
