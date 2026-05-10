"""external tickets and ban appeals

Revision ID: b12_external_tickets_ban_appeals
Revises: b11_mobile_login_settings
Create Date: 2026-05-10
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b12_external_tickets_ban_appeals"
down_revision: Union[str, Sequence[str], None] = "b11_mobile_login_settings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column(
            "service_rules_text",
            sa.Text(),
            nullable=False,
            server_default=(
                "Пользуйтесь сервисом добросовестно: не дублируйте заявки, указывайте достоверную информацию "
                "и соблюдайте уважительный тон в общении."
            ),
        ),
    )
    op.alter_column("app_settings", "service_rules_text", server_default=None)

    op.add_column(
        "tickets",
        sa.Column("is_external_request", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("tickets", sa.Column("external_contact_phone", sa.String(), nullable=True))
    op.alter_column("tickets", "is_external_request", server_default=None)

    op.create_table(
        "ban_conversations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("resident_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["resident_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("resident_id", name="uq_ban_conversations_resident_id"),
    )
    op.create_index(op.f("ix_ban_conversations_id"), "ban_conversations", ["id"], unique=False)
    op.create_index(op.f("ix_ban_conversations_resident_id"), "ban_conversations", ["resident_id"], unique=False)

    op.create_table(
        "ban_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("sender_id", sa.Integer(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["ban_conversations.id"]),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ban_messages_id"), "ban_messages", ["id"], unique=False)
    op.create_index(op.f("ix_ban_messages_conversation_id"), "ban_messages", ["conversation_id"], unique=False)
    op.create_index(op.f("ix_ban_messages_sender_id"), "ban_messages", ["sender_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ban_messages_sender_id"), table_name="ban_messages")
    op.drop_index(op.f("ix_ban_messages_conversation_id"), table_name="ban_messages")
    op.drop_index(op.f("ix_ban_messages_id"), table_name="ban_messages")
    op.drop_table("ban_messages")

    op.drop_index(op.f("ix_ban_conversations_resident_id"), table_name="ban_conversations")
    op.drop_index(op.f("ix_ban_conversations_id"), table_name="ban_conversations")
    op.drop_table("ban_conversations")

    op.drop_column("tickets", "external_contact_phone")
    op.drop_column("tickets", "is_external_request")
    op.drop_column("app_settings", "service_rules_text")
