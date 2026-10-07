"""Durable explicit shopper preferences."""

import sqlalchemy as sa
from alembic import op

revision = "019_shopper_preferences"
down_revision = "018_payment_email_outbox"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "shopper_preferences",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "owner_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column("explicit", sa.JSON(), nullable=False),
    )


def downgrade():
    op.drop_table("shopper_preferences")
