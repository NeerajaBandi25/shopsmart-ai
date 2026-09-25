"""Merge the independent cart and order schema revisions."""

revision = "006_merge_cart_order_heads"
down_revision = ("004_create_cart_tables", "005_create_order_tables")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Join the cart and order migration histories."""


def downgrade() -> None:
    """Separate the cart and order migration histories."""