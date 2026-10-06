"""Create owned AI document and conversation tables."""

import sqlalchemy as sa
from alembic import op

revision = "007_create_ai_tables"
down_revision = "006_merge_cart_order_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    uuid = sa.Uuid()

    def common_columns() -> list[sa.Column]:
        return [
            sa.Column("id", uuid, nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        ]

    op.create_table(
        "ai_documents",
        *common_columns(),
        sa.Column("owner_id", uuid, nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("source_name", sa.String(255), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("active_version_id", uuid, nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "content_hash", name="uq_ai_documents_owner_hash"),
    )
    op.create_index("ix_ai_documents_owner_created", "ai_documents", ["owner_id", "created_at"])
    op.create_table(
        "ai_document_versions",
        *common_columns(),
        sa.Column("document_id", uuid, nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failure_reason", sa.String(255), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["ai_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "version_number", name="uq_ai_document_versions_number"),
        sa.UniqueConstraint("document_id", "id", name="uq_ai_document_versions_document_id"),
    )
    op.create_index("ix_ai_document_versions_status", "ai_document_versions", ["status"])
    op.create_table(
        "ai_document_chunks",
        *common_columns(),
        sa.Column("document_id", uuid, nullable=False),
        sa.Column("version_id", uuid, nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("source_label", sa.String(255), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("embedding", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["ai_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["version_id"], ["ai_document_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["document_id", "version_id"],
            ["ai_document_versions.document_id", "ai_document_versions.id"],
            name="fk_ai_chunks_document_version",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version_id", "chunk_index", name="uq_ai_chunks_version_index"),
    )
    op.create_foreign_key(
        "fk_ai_documents_active_version",
        "ai_documents",
        "ai_document_versions",
        ["active_version_id"],
        ["id"],
    )
    op.create_index(
        "ix_ai_chunks_document_active", "ai_document_chunks", ["document_id", "version_id"]
    )
    op.create_table(
        "ai_conversations",
        *common_columns(),
        sa.Column("owner_id", uuid, nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ai_conversations_owner_created", "ai_conversations", ["owner_id", "created_at"]
    )
    op.create_table(
        "ai_chat_messages",
        *common_columns(),
        sa.Column("conversation_id", uuid, nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("citations", sa.JSON(), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["conversation_id"], ["ai_conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ai_messages_conversation_created", "ai_chat_messages", ["conversation_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_ai_messages_conversation_created", table_name="ai_chat_messages")
    op.drop_table("ai_chat_messages")
    op.drop_index("ix_ai_conversations_owner_created", table_name="ai_conversations")
    op.drop_table("ai_conversations")
    op.drop_index("ix_ai_chunks_document_active", table_name="ai_document_chunks")
    op.drop_table("ai_document_chunks")
    op.drop_index("ix_ai_document_versions_status", table_name="ai_document_versions")
    op.drop_table("ai_document_versions")
    op.drop_index("ix_ai_documents_owner_created", table_name="ai_documents")
    op.drop_table("ai_documents")
