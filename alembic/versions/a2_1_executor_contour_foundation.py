"""phase a2.1 executor contour foundation

Revision ID: a2_1_executor_foundation
Revises: REPLACE_WITH_CURRENT_HEAD
Create Date: 2026-04-17 18:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a2_1_executor_foundation"
down_revision: Union[str, Sequence[str], None] = "a1_house_structure_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("login", sa.String(), nullable=True))
    op.add_column("users", sa.Column("contact_phone", sa.String(), nullable=True))

    op.execute("UPDATE users SET login = phone WHERE login IS NULL AND phone IS NOT NULL")
    op.execute("UPDATE users SET login = 'user_' || id::text WHERE login IS NULL")

    op.alter_column("users", "login", nullable=False)
    op.create_index("ix_users_login", "users", ["login"], unique=True)

    op.create_table(
        "executor_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("house_id", sa.Integer(), nullable=True),
        sa.Column("first_name", sa.String(), nullable=False),
        sa.Column("last_name", sa.String(), nullable=False),
        sa.Column("middle_name", sa.String(), nullable=True),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["house_id"], ["houses.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id")
    )
    op.create_index(op.f("ix_executor_profiles_id"), "executor_profiles", ["id"], unique=False)
    op.create_index(op.f("ix_executor_profiles_user_id"), "executor_profiles", ["user_id"], unique=False)
    op.create_index(op.f("ix_executor_profiles_house_id"), "executor_profiles", ["house_id"], unique=False)

    op.create_table(
        "specialties",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name")
    )
    op.create_index(op.f("ix_specialties_id"), "specialties", ["id"], unique=False)
    op.create_index(op.f("ix_specialties_code"), "specialties", ["code"], unique=True)

    op.create_table(
        "executor_specialties",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("executor_id", sa.Integer(), nullable=False),
        sa.Column("specialty_id", sa.Integer(), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.ForeignKeyConstraint(["executor_id"], ["executor_profiles.id"]),
        sa.ForeignKeyConstraint(["specialty_id"], ["specialties.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("executor_id", "specialty_id", name="uq_executor_specialty")
    )
    op.create_index(op.f("ix_executor_specialties_id"), "executor_specialties", ["id"], unique=False)
    op.create_index(op.f("ix_executor_specialties_executor_id"), "executor_specialties", ["executor_id"], unique=False)
    op.create_index(op.f("ix_executor_specialties_specialty_id"), "executor_specialties", ["specialty_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_executor_specialties_specialty_id"), table_name="executor_specialties")
    op.drop_index(op.f("ix_executor_specialties_executor_id"), table_name="executor_specialties")
    op.drop_index(op.f("ix_executor_specialties_id"), table_name="executor_specialties")
    op.drop_table("executor_specialties")

    op.drop_index(op.f("ix_specialties_code"), table_name="specialties")
    op.drop_index(op.f("ix_specialties_id"), table_name="specialties")
    op.drop_table("specialties")

    op.drop_index(op.f("ix_executor_profiles_house_id"), table_name="executor_profiles")
    op.drop_index(op.f("ix_executor_profiles_user_id"), table_name="executor_profiles")
    op.drop_index(op.f("ix_executor_profiles_id"), table_name="executor_profiles")
    op.drop_table("executor_profiles")

    op.drop_index("ix_users_login", table_name="users")
    op.drop_column("users", "contact_phone")
    op.drop_column("users", "login")