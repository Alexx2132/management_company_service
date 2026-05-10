"""phase a1 house structure entrances apartments

Revision ID: a1_house_structure_01
Revises: REPLACE_WITH_CURRENT_HEAD
Create Date: 2026-04-17 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1_house_structure_01"
down_revision: Union[str, Sequence[str], None] = "616f9835768c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "house_entrances",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("house_id", sa.Integer(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("floors_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("apartments_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["house_id"], ["houses.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("house_id", "number", name="uq_house_entrances_house_number"),
    )
    op.create_index(op.f("ix_house_entrances_id"), "house_entrances", ["id"], unique=False)
    op.create_index(op.f("ix_house_entrances_house_id"), "house_entrances", ["house_id"], unique=False)

    op.create_table(
        "apartments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("house_id", sa.Integer(), nullable=False),
        sa.Column("entrance_id", sa.Integer(), nullable=False),
        sa.Column("floor_number", sa.Integer(), nullable=False),
        sa.Column("apartment_number", sa.String(), nullable=False),
        sa.Column("rooms_count", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["entrance_id"], ["house_entrances.id"]),
        sa.ForeignKeyConstraint(["house_id"], ["houses.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("house_id", "apartment_number", name="uq_apartments_house_apartment_number"),
    )
    op.create_index(op.f("ix_apartments_id"), "apartments", ["id"], unique=False)
    op.create_index(op.f("ix_apartments_house_id"), "apartments", ["house_id"], unique=False)
    op.create_index(op.f("ix_apartments_entrance_id"), "apartments", ["entrance_id"], unique=False)

    op.add_column("users", sa.Column("apartment_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_users_apartment_id_apartments",
        "users",
        "apartments",
        ["apartment_id"],
        ["id"],
    )
    op.create_index("ix_users_apartment_id", "users", ["apartment_id"], unique=False)

    op.add_column("tickets", sa.Column("apartment_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_tickets_apartment_id_apartments",
        "tickets",
        "apartments",
        ["apartment_id"],
        ["id"],
    )
    op.create_index("ix_tickets_apartment_id", "tickets", ["apartment_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_tickets_apartment_id", table_name="tickets")
    op.drop_constraint("fk_tickets_apartment_id_apartments", "tickets", type_="foreignkey")
    op.drop_column("tickets", "apartment_id")

    op.drop_index("ix_users_apartment_id", table_name="users")
    op.drop_constraint("fk_users_apartment_id_apartments", "users", type_="foreignkey")
    op.drop_column("users", "apartment_id")

    op.drop_index(op.f("ix_apartments_entrance_id"), table_name="apartments")
    op.drop_index(op.f("ix_apartments_house_id"), table_name="apartments")
    op.drop_index(op.f("ix_apartments_id"), table_name="apartments")
    op.drop_table("apartments")

    op.drop_index(op.f("ix_house_entrances_house_id"), table_name="house_entrances")
    op.drop_index(op.f("ix_house_entrances_id"), table_name="house_entrances")
    op.drop_table("house_entrances")