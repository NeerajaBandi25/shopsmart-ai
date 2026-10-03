"""Add authoritative promotions and immutable order pricing snapshots.

Revision ID: 013_promotions_discount_engine
Revises: 012_product_structured_category
Create Date: 2026-10-03
"""

import sqlalchemy as sa
from alembic import op

revision = "013_promotions_discount_engine"
down_revision = "012_product_structured_category"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "promotions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("code", sa.String(length=32), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("promotion_type", sa.String(length=16), nullable=False),
        sa.Column("value", sa.Integer(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("scope_type", sa.String(length=16), nullable=False),
        sa.Column("scope_category", sa.String(length=32), nullable=True),
        sa.Column("scope_product_id", sa.Uuid(), nullable=True),
        sa.Column("min_cart_total_cents", sa.Integer(), nullable=True),
        sa.Column("max_discount_cents", sa.Integer(), nullable=True),
        sa.Column("eligible_user_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "promotion_type = 'percentage' AND value BETWEEN 1 AND 100 "
            "OR promotion_type = 'fixed' AND value > 0",
            name="ck_promotions_value_valid",
        ),
        sa.CheckConstraint(
            "scope_type = 'all' AND scope_category IS NULL AND scope_product_id IS NULL "
            "OR scope_type = 'category' AND scope_category IS NOT NULL "
            "AND scope_product_id IS NULL "
            "OR scope_type = 'product' AND scope_category IS NULL "
            "AND scope_product_id IS NOT NULL",
            name="ck_promotions_scope_target_consistent",
        ),
        sa.CheckConstraint(
            "scope_category IS NULL OR scope_category IN "
            "('laptops', 'phones', 'accessories', 'footwear', 'fashion', 'appliances', "
            "'home', 'beauty', 'groceries')",
            name="ck_promotions_scope_category_canonical",
        ),
        sa.CheckConstraint("ends_at > starts_at", name="ck_promotions_window_valid"),
        sa.CheckConstraint(
            "min_cart_total_cents IS NULL OR min_cart_total_cents >= 0",
            name="ck_promotions_minimum_non_negative",
        ),
        sa.CheckConstraint(
            "max_discount_cents IS NULL OR max_discount_cents > 0",
            name="ck_promotions_maximum_positive",
        ),
        sa.ForeignKeyConstraint(["scope_product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["eligible_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_promotions_code"),
    )
    op.create_index(
        "uq_promotions_code_lower",
        "promotions",
        [sa.text("lower(code)")],
        unique=True,
        postgresql_where=sa.text("code IS NOT NULL"),
        sqlite_where=sa.text("code IS NOT NULL"),
    )
    op.create_index("ix_promotions_active_window", "promotions", ["active", "starts_at", "ends_at"])
    op.create_index("ix_promotions_scope_category", "promotions", ["scope_category"])
    op.create_index("ix_promotions_eligible_user", "promotions", ["eligible_user_id"])

    op.add_column("carts", sa.Column("coupon_code", sa.String(length=32), nullable=True))
    op.add_column("orders", sa.Column("subtotal_cents", sa.Integer(), nullable=True))
    op.add_column(
        "orders",
        sa.Column("discount_total_cents", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("orders", sa.Column("promotion_snapshot", sa.JSON(), nullable=True))
    op.execute(
        "UPDATE orders SET subtotal_cents = total_cents, discount_total_cents = 0, "
        "promotion_snapshot = '[]'"
    )
    op.alter_column("orders", "subtotal_cents", nullable=False)
    op.alter_column("orders", "promotion_snapshot", nullable=False)
    op.create_check_constraint("ck_orders_subtotal_non_negative", "orders", "subtotal_cents >= 0")
    op.create_check_constraint(
        "ck_orders_discount_within_subtotal",
        "orders",
        "discount_total_cents >= 0 AND discount_total_cents <= subtotal_cents",
    )
    op.create_check_constraint(
        "ck_orders_pricing_total_consistent",
        "orders",
        "total_cents = subtotal_cents - discount_total_cents",
    )


def downgrade() -> None:
    op.drop_constraint("ck_orders_pricing_total_consistent", "orders", type_="check")
    op.drop_constraint("ck_orders_discount_within_subtotal", "orders", type_="check")
    op.drop_constraint("ck_orders_subtotal_non_negative", "orders", type_="check")
    op.drop_column("orders", "promotion_snapshot")
    op.drop_column("orders", "discount_total_cents")
    op.drop_column("orders", "subtotal_cents")
    op.drop_column("carts", "coupon_code")
    op.drop_index("ix_promotions_eligible_user", table_name="promotions")
    op.drop_index("ix_promotions_scope_category", table_name="promotions")
    op.drop_index("ix_promotions_active_window", table_name="promotions")
    op.drop_index("uq_promotions_code_lower", table_name="promotions")
    op.drop_table("promotions")
