"""category types and ticket place category

Revision ID: b10_category_types_ticket_place
Revises: b9_ticket_contact_visibility
Create Date: 2026-05-09
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b10_category_types_ticket_place"
down_revision: Union[str, Sequence[str], None] = "b9_ticket_contact_visibility"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "categories",
        sa.Column("category_type", sa.String(length=32), nullable=False, server_default="problem"),
    )
    op.alter_column("categories", "category_type", server_default=None)

    op.drop_index("ix_categories_name", table_name="categories")
    op.create_index("ix_categories_name", "categories", ["name"], unique=False)
    op.create_index("ix_categories_category_type", "categories", ["category_type"], unique=False)
    op.create_unique_constraint("uq_categories_name_type", "categories", ["name", "category_type"])

    op.add_column("tickets", sa.Column("place_category_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_tickets_place_category_id_categories",
        "tickets",
        "categories",
        ["place_category_id"],
        ["id"],
    )

    op.execute(
        """
        INSERT INTO categories (name, category_type)
        VALUES
            ('Квартира', 'location'),
            ('Подъезд', 'location'),
            ('Двор (улица)', 'location')
        ON CONFLICT ON CONSTRAINT uq_categories_name_type DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_constraint("fk_tickets_place_category_id_categories", "tickets", type_="foreignkey")
    op.drop_column("tickets", "place_category_id")

    op.execute("DELETE FROM categories WHERE category_type = 'location'")

    op.drop_constraint("uq_categories_name_type", "categories", type_="unique")
    op.drop_index("ix_categories_category_type", table_name="categories")
    op.drop_index("ix_categories_name", table_name="categories")
    op.create_index("ix_categories_name", "categories", ["name"], unique=True)
    op.drop_column("categories", "category_type")
