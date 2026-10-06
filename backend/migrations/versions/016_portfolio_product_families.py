"""Allow the requested portfolio product families without rewriting existing rows.

Revision ID: 016_portfolio_product_families
Revises: 015_portfolio_catalog_categories
Create Date: 2026-10-03
"""

from alembic import op

revision = "016_portfolio_product_families"
down_revision = "015_portfolio_catalog_categories"
branch_labels = None
depends_on = None

PREVIOUS_CATEGORIES = (
    "'laptops', 'phones', 'accessories', 'footwear', 'fashion', 'appliances', "
    "'home', 'beauty', 'groceries', 'furniture', 'sports', 'toys', 'books', "
    "'automotive', 'pet_supplies'"
)
PORTFOLIO_CATEGORIES = (
    "'smartphones', 'headphones', 'smartwatches', 'tablets', 'cameras', "
    "'televisions', 'gaming', 'home_appliances', 'kitchen_appliances', 'home_living'"
)


def upgrade() -> None:
    categories = f"{PREVIOUS_CATEGORIES}, {PORTFOLIO_CATEGORIES}"
    with op.batch_alter_table("products") as batch_op:
        batch_op.drop_constraint("ck_products_category_canonical", type_="check")
        batch_op.create_check_constraint(
            "ck_products_category_canonical",
            f"category IS NULL OR category IN ({categories})",
        )


def downgrade() -> None:
    with op.batch_alter_table("products") as batch_op:
        batch_op.drop_constraint("ck_products_category_canonical", type_="check")
        batch_op.create_check_constraint(
            "ck_products_category_canonical",
            f"category IS NULL OR category IN ({PREVIOUS_CATEGORIES})",
        )
