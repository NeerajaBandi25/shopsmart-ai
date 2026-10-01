"""Add an optional authoritative product category."""

import sqlalchemy as sa
from alembic import op

revision = "012_product_structured_category"
down_revision = "011_resequence_assistant_history"
branch_labels = None
depends_on = None

CATEGORIES = "'laptops', 'phones', 'accessories', 'footwear', 'fashion', 'appliances', 'home', 'beauty', 'groceries'"


def upgrade() -> None:
    op.add_column("products", sa.Column("category", sa.String(length=32), nullable=True))
    op.create_check_constraint(
        "ck_products_category_canonical",
        "products",
        f"category IS NULL OR category IN ({CATEGORIES})",
    )
    op.create_index("ix_products_category", "products", ["category"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_products_category", table_name="products")
    op.drop_constraint("ck_products_category_canonical", "products", type_="check")
    op.drop_column("products", "category")
