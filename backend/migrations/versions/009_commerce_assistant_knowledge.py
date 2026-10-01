"""Add assistant context and server-owned knowledge corpus."""

import sqlalchemy as sa
from alembic import op

revision = "009_commerce_assistant_knowledge"
down_revision = "008_add_ai_data_classification"
branch_labels = None
depends_on = None


def _common_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    ]


def upgrade() -> None:
    op.add_column(
        "ai_conversations",
        sa.Column("context", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.add_column("ai_chat_messages", sa.Column("result_data", sa.JSON(), nullable=True))
    op.create_table(
        "ai_knowledge_sources",
        *_common_columns(),
        sa.Column("source_key", sa.String(100), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("active_version_id", sa.Uuid(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_key", name="uq_ai_knowledge_sources_source_key"),
    )
    op.create_table(
        "ai_knowledge_versions",
        *_common_columns(),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="ready"),
        sa.ForeignKeyConstraint(["source_id"], ["ai_knowledge_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", "version_number", name="uq_ai_knowledge_version_number"),
        sa.UniqueConstraint("source_id", "id", name="uq_ai_knowledge_version_source_id"),
    )
    op.create_foreign_key(
        "fk_ai_knowledge_active_version",
        "ai_knowledge_sources",
        "ai_knowledge_versions",
        ["id", "active_version_id"],
        ["source_id", "id"],
    )
    op.create_table(
        "ai_knowledge_chunks",
        *_common_columns(),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("source_label", sa.String(255), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("embedding", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["version_id"], ["ai_knowledge_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version_id", "chunk_index", name="uq_ai_knowledge_chunk_index"),
    )
    op.create_index("ix_ai_knowledge_chunks_version", "ai_knowledge_chunks", ["version_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_knowledge_chunks_version", table_name="ai_knowledge_chunks")
    op.drop_table("ai_knowledge_chunks")
    op.drop_constraint("fk_ai_knowledge_active_version", "ai_knowledge_sources", type_="foreignkey")
    op.drop_table("ai_knowledge_versions")
    op.drop_table("ai_knowledge_sources")
    op.drop_column("ai_chat_messages", "result_data")
    op.drop_column("ai_conversations", "context")
