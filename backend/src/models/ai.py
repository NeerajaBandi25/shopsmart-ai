"""Persistent AI document and conversation entities."""

from uuid import UUID

from sqlalchemy import (
    JSON,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import BaseModel


class Document(BaseModel):
    __tablename__ = "ai_documents"

    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    classification: Mapped[str] = mapped_column(String(16), nullable=False, default="PRIVATE")
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    active_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "ai_document_versions.id", use_alter=True, name="fk_ai_documents_active_version"
        ),
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint("owner_id", "content_hash", name="uq_ai_documents_owner_hash"),
        Index("ix_ai_documents_owner_created", "owner_id", "created_at"),
    )


class DocumentVersion(BaseModel):
    __tablename__ = "ai_document_versions"

    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("ai_documents.id", ondelete="CASCADE"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        UniqueConstraint("document_id", "version_number", name="uq_ai_document_versions_number"),
        UniqueConstraint("document_id", "id", name="uq_ai_document_versions_document_id"),
        Index("ix_ai_document_versions_status", "status"),
    )


class DocumentChunk(BaseModel):
    __tablename__ = "ai_document_chunks"

    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("ai_documents.id", ondelete="CASCADE"), nullable=False
    )
    version_id: Mapped[UUID] = mapped_column(
        ForeignKey("ai_document_versions.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_label: Mapped[str] = mapped_column(String(255), nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding: Mapped[list[float]] = mapped_column(JSON, nullable=False)

    __table_args__ = (
        UniqueConstraint("version_id", "chunk_index", name="uq_ai_chunks_version_index"),
        ForeignKeyConstraint(
            ["document_id", "version_id"],
            ["ai_document_versions.document_id", "ai_document_versions.id"],
            name="fk_ai_chunks_document_version",
        ),
        Index("ix_ai_chunks_document_active", "document_id", "version_id"),
    )


class Conversation(BaseModel):
    __tablename__ = "ai_conversations"

    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="New conversation")
    context: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    __table_args__ = (Index("ix_ai_conversations_owner_created", "owner_id", "created_at"),)


class ChatMessage(BaseModel):
    __tablename__ = "ai_chat_messages"

    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("ai_conversations.id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    result_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    client_request_id: Mapped[UUID | None] = mapped_column(nullable=True)
    client_request_owner_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    client_request_conversation_id: Mapped[UUID | None] = mapped_column(nullable=True)

    __table_args__ = (
        Index("ix_ai_messages_conversation_created", "conversation_id", "created_at"),
        Index("ix_ai_messages_conversation_sequence", "conversation_id", "sequence"),
        Index(
            "uq_ai_messages_owner_request_id",
            "client_request_owner_id",
            "client_request_id",
            unique=True,
        ),
        UniqueConstraint(
            "conversation_id", "sequence", name="uq_ai_messages_conversation_sequence"
        ),
    )


class KnowledgeSource(BaseModel):
    __tablename__ = "ai_knowledge_sources"

    source_key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    active_version_id: Mapped[UUID | None] = mapped_column(nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["id", "active_version_id"],
            ["ai_knowledge_versions.source_id", "ai_knowledge_versions.id"],
            name="fk_ai_knowledge_active_version",
            use_alter=True,
        ),
    )


class KnowledgeVersion(BaseModel):
    __tablename__ = "ai_knowledge_versions"

    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("ai_knowledge_sources.id", ondelete="CASCADE"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ready")

    __table_args__ = (
        UniqueConstraint("source_id", "version_number", name="uq_ai_knowledge_version_number"),
        UniqueConstraint("source_id", "id", name="uq_ai_knowledge_version_source_id"),
    )


class KnowledgeChunk(BaseModel):
    __tablename__ = "ai_knowledge_chunks"

    version_id: Mapped[UUID] = mapped_column(
        ForeignKey("ai_knowledge_versions.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_label: Mapped[str] = mapped_column(String(255), nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding: Mapped[list[float]] = mapped_column(JSON, nullable=False)

    __table_args__ = (
        UniqueConstraint("version_id", "chunk_index", name="uq_ai_knowledge_chunk_index"),
        Index("ix_ai_knowledge_chunks_version", "version_id"),
    )
