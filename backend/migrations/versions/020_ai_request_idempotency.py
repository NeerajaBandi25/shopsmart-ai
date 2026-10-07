"""Persist client request keys for assistant replay protection."""

import sqlalchemy as sa
from alembic import op

revision = "020_ai_request_idempotency"
down_revision = "019_shopper_preferences"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "ai_chat_messages",
        sa.Column("client_request_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "ai_chat_messages",
        sa.Column(
            "client_request_owner_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.add_column(
        "ai_chat_messages",
        sa.Column("client_request_conversation_id", sa.Uuid(), nullable=True),
    )
    op.create_index(
        "uq_ai_messages_owner_request_id",
        "ai_chat_messages",
        ["client_request_owner_id", "client_request_id"],
        unique=True,
    )


def downgrade():
    op.drop_index("uq_ai_messages_owner_request_id", table_name="ai_chat_messages")
    op.drop_column("ai_chat_messages", "client_request_conversation_id")
    op.drop_column("ai_chat_messages", "client_request_owner_id")
    op.drop_column("ai_chat_messages", "client_request_id")
