"""Add nullable product merchandising and image provenance fields.

Revision ID: 014_product_merchandising
Revises: 013_promotions_discount_engine
Create Date: 2026-10-04
"""

import sqlalchemy as sa
from alembic import op

revision = "014_product_merchandising"
down_revision = "013_promotions_discount_engine"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("products") as batch_op:
        batch_op.add_column(sa.Column("brand", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("list_price", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("image_url", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("image_alt", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("image_source_url", sa.String(length=1000), nullable=True))
        batch_op.add_column(sa.Column("image_creator", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("image_license", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("image_license_url", sa.String(length=1000), nullable=True))
        batch_op.add_column(sa.Column("image_sha256", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("specifications", sa.JSON(), nullable=True))
        batch_op.create_check_constraint(
            "ck_products_list_price_not_below_price",
            "list_price IS NULL OR list_price >= price",
        )


def downgrade() -> None:
    with op.batch_alter_table("products") as batch_op:
        batch_op.drop_constraint("ck_products_list_price_not_below_price", type_="check")
        batch_op.drop_column("specifications")
        batch_op.drop_column("image_sha256")
        batch_op.drop_column("image_license_url")
        batch_op.drop_column("image_license")
        batch_op.drop_column("image_creator")
        batch_op.drop_column("image_source_url")
        batch_op.drop_column("image_alt")
        batch_op.drop_column("image_url")
        batch_op.drop_column("list_price")
        batch_op.drop_column("brand")
