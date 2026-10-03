"""Correct backfilled message order for transaction-identical timestamps."""

import sqlalchemy as sa
from alembic import op

revision = "011_resequence_assistant_history"
down_revision = "010_order_assistant_messages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_ai_messages_conversation_sequence", table_name="ai_chat_messages")
    op.drop_constraint("uq_ai_messages_conversation_sequence", "ai_chat_messages", type_="unique")
    op.execute(
        sa.text(
            """
            WITH ranked_messages AS (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY conversation_id
                           ORDER BY created_at,
                                    CASE role
                                        WHEN 'user' THEN 0
                                        WHEN 'assistant' THEN 1
                                        ELSE 2
                                    END,
                                    id
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
