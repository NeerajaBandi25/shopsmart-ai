"""Add stable ordering for assistant conversation messages."""

import sqlalchemy as sa
from alembic import op

revision = "010_order_assistant_messages"
down_revision = "009_commerce_assistant_knowledge"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ai_chat_messages", sa.Column("sequence", sa.Integer(), nullable=True))
    op.execute(
        sa.text(
            """
            WITH ranked_messages AS (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY conversation_id ORDER BY created_at, id
                       ) AS message_sequence
                FROM ai_chat_messages
            )
            UPDATE ai_chat_messages AS message
            SET sequence = ranked_messages.message_sequence
            FROM ranked_messages
            WHERE message.id = ranked_messages.id
            """
        )
    )
    op.alter_column("ai_chat_messages", "sequence", nullable=False)
    op.create_unique_constraint(
        "uq_ai_messages_conversation_sequence",
        "ai_chat_messages",
        ["conversation_id", "sequence"],
    )
    op.create_index(
        "ix_ai_messages_conversation_sequence",
        "ai_chat_messages",
        ["conversation_id", "sequence"],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_messages_conversation_sequence", table_name="ai_chat_messages")
    op.drop_constraint("uq_ai_messages_conversation_sequence", "ai_chat_messages", type_="unique")
    op.drop_column("ai_chat_messages", "sequence")
