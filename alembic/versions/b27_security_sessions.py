"""Версия сессий и общие для всех процессов ограничения попыток входа."""
from alembic import op
import sqlalchemy as sa

revision = "b27_security_sessions"
down_revision = "b26_exec_reviews"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("session_version", sa.Integer(), nullable=False, server_default="0"))
    op.create_table("auth_rate_limits",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_auth_rate_limits_expires_at", "auth_rate_limits", ["expires_at"])


def downgrade():
    op.drop_table("auth_rate_limits")
    op.drop_column("users", "session_version")
