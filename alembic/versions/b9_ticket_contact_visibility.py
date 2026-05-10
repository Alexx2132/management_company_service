"""add ticket contact phone visibility flag

Revision ID: b9_ticket_contact_visibility
Revises: b8_push_tokens
Create Date: 2026-05-08
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b9_ticket_contact_visibility"
down_revision: Union[str, Sequence[str], None] = "b8_push_tokens"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tickets",
        sa.Column("show_contact_phone", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("tickets", "show_contact_phone", server_default=None)


def downgrade() -> None:
    op.drop_column("tickets", "show_contact_phone")
