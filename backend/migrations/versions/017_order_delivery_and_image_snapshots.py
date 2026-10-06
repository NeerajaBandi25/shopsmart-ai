"""Add delivery details and immutable product-image references to orders.

Revision ID: 017_order_delivery_images
Revises: 016_portfolio_product_families
Create Date: 2026-10-03
"""

import sqlalchemy as sa
from alembic import op

revision = "017_order_delivery_images"
down_revision = "016_portfolio_product_families"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("orders") as batch_op:
        batch_op.add_column(sa.Column("delivery_address", sa.JSON(), nullable=True))
    with op.batch_alter_table("order_items") as batch_op:
        batch_op.add_column(sa.Column("product_image_url", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("product_image_alt", sa.String(length=255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("order_items") as batch_op:
        batch_op.drop_column("product_image_alt")
        batch_op.drop_column("product_image_url")
    with op.batch_alter_table("orders") as batch_op:
        batch_op.drop_column("delivery_address")
