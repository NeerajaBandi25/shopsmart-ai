"""Add explicit AI document data classification."""

import sqlalchemy as sa
from alembic import op

revision = "008_add_ai_data_classification"
down_revision = "007_create_ai_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ai_documents",
        sa.Column("classification", sa.String(16), nullable=False, server_default="PRIVATE"),
    )


def downgrade() -> None:
    op.drop_column("ai_documents", "classification")
