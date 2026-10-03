"""Expand canonical product categories for the portfolio catalog.

Revision ID: 015_portfolio_catalog_categories
Revises: 014_product_merchandising
Create Date: 2026-10-03
"""

from alembic import op

revision = "015_portfolio_catalog_categories"
down_revision = "014_product_merchandising"
branch_labels = None
depends_on = None

CATEGORIES = (
    "'laptops', 'phones', 'accessories', 'footwear', 'fashion', 'appliances', "
    "'home', 'beauty', 'groceries', 'furniture', 'sports', 'toys', 'books', "
    "'automotive', 'pet_supplies'"
)
PREVIOUS_CATEGORIES = (
    "'laptops', 'phones', 'accessories', 'footwear', 'fashion', 'appliances', "
    "'home', 'beauty', 'groceries'"
)


def upgrade() -> None:
    with op.batch_alter_table("products") as batch_op:
        batch_op.drop_constraint("ck_products_category_canonical", type_="check")
        batch_op.create_check_constraint(
            "ck_products_category_canonical",
            f"category IS NULL OR category IN ({CATEGORIES})",
        )


def downgrade() -> None:
    with op.batch_alter_table("products") as batch_op:
        batch_op.drop_constraint("ck_products_category_canonical", type_="check")
        batch_op.create_check_constraint(
            "ck_products_category_canonical",
            f"category IS NULL OR category IN ({PREVIOUS_CATEGORIES})",
        )
