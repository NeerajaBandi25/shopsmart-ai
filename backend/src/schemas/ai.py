"""AI API contracts."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DocumentTextRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    source_name: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1)


class DocumentResponse(BaseModel):
    id: UUID
    title: str
    source_name: str
    classification: str
    status: str
    created_at: datetime
    chunk_count: int


class Citation(BaseModel):
    citation_id: str
    document_id: UUID
    knowledge_version_id: UUID | None = None
    source_label: str
    page_number: int | None = None
    chunk_index: int


class ChatRequest(BaseModel):
    conversation_id: UUID | None = None
    question: str = Field(min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    conversation_id: UUID
    message_id: UUID
    answer: str
    answerable: bool
    reason: str | None = None
    citations: list[Citation]
    intent: str = "UNSUPPORTED"
    result_data: dict | None = None


class ConversationResponse(BaseModel):
    id: UUID
    title: str
    created_at: datetime


class MessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    citations: list[Citation] = Field(default_factory=list)
    result_data: dict | None = None
    created_at: datetime
