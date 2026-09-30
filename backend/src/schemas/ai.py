"""AI API contracts."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DocumentTextRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    source_name: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1)
    classification: str = Field(default="PRIVATE", pattern="^(PUBLIC|INTERNAL|PRIVATE|SENSITIVE)$")


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
    source_label: str
    page_number: int | None = None
    chunk_index: int


class ChatRequest(BaseModel):
    conversation_id: UUID | None = None
    question: str = Field(min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    conversation_id: UUID
    answer: str
    answerable: bool
    citations: list[Citation]
    retrieval_count: int
    token_count: int
    estimated_cost_usd: float
    provider: str = "deterministic"
    model: str = "local-deterministic-v1"
    fallback_used: bool = False


class ConversationResponse(BaseModel):
    id: UUID
    title: str
    created_at: datetime


class MessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    citations: list[Citation] = Field(default_factory=list)
    created_at: datetime
