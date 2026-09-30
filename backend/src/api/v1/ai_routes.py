"""Authenticated document assistant API."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.deps import get_current_user, get_db, require_csrf_token
from src.core.exceptions import ValidationError
from src.models.ai import Document, DocumentChunk
from src.schemas.ai import (
    ChatRequest,
    ChatResponse,
    ConversationResponse,
    DocumentResponse,
    DocumentTextRequest,
    MessageResponse,
)
from src.services.ai_chat import ChatService
from src.services.ai_ingestion import DocumentIngestionService, extract_document_text

router = APIRouter(prefix="/ai", tags=["AI assistant"])


async def _ingest(
    user_id: UUID, title: str, source_name: str, content: str, classification: str, db: AsyncSession
) -> DocumentResponse:
    document = await DocumentIngestionService(db).ingest(
        user_id, title, source_name, content, classification
    )
    chunk_count = len(
        (
            await db.execute(
                select(DocumentChunk.id).where(DocumentChunk.document_id == document.id)
            )
        ).all()
    )
    return DocumentResponse(
        id=document.id,
        title=document.title,
        source_name=document.source_name,
        classification=document.classification,
        status="ready",
        created_at=document.created_at,
        chunk_count=chunk_count,
    )


@router.post("/documents", response_model=DocumentResponse, status_code=201)
async def ingest_document(
    request: DocumentTextRequest,
    user_id: UUID = Depends(get_current_user),
    _csrf: None = Depends(require_csrf_token),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    return await _ingest(
        user_id, request.title, request.source_name, request.content, request.classification, db
    )


@router.post("/documents/upload", response_model=DocumentResponse, status_code=201)
async def upload_document(
    request: Request,
    title: str = Query(min_length=1, max_length=255),
    source_name: str = Query(min_length=1, max_length=255),
    user_id: UUID = Depends(get_current_user),
    _csrf: None = Depends(require_csrf_token),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
    body = await request.body()
    if len(body) > 2_500_000:
        raise ValidationError("Document exceeds the maximum size", "document_too_large")
    classification = request.headers.get("x-data-classification", "PRIVATE").upper()
    return await _ingest(
        user_id, title, source_name, extract_document_text(body, content_type), classification, db
    )


@router.get("/documents", response_model=list[DocumentResponse])
async def list_documents(
    user_id: UUID = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[DocumentResponse]:
    documents = (
        (
            await db.execute(
                select(Document)
                .where(Document.owner_id == user_id)
                .order_by(Document.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    results = []
    for document in documents:
        chunk_count = len(
            (
                await db.execute(
                    select(DocumentChunk.id).where(DocumentChunk.document_id == document.id)
                )
            ).all()
        )
        results.append(
            DocumentResponse(
                id=document.id,
                title=document.title,
                source_name=document.source_name,
                classification=document.classification,
                status="ready",
                created_at=document.created_at,
                chunk_count=chunk_count,
            )
        )
    return results


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    user_id: UUID = Depends(get_current_user),
    _csrf: None = Depends(require_csrf_token),
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    return ChatResponse(
        **await ChatService(db).answer(user_id, request.question, request.conversation_id)
    )


@router.get("/conversations", response_model=list[ConversationResponse])
async def list_conversations(
    user_id: UUID = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[ConversationResponse]:
    return [
        ConversationResponse(id=item.id, title=item.title, created_at=item.created_at)
        for item in await ChatService(db).conversations.list_owned(user_id)
    ]


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageResponse])
async def conversation_messages(
    conversation_id: UUID,
    user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MessageResponse]:
    repository = ChatService(db).conversations
    if not await repository.get_owned(conversation_id, user_id):
        raise ValidationError("Conversation not found", "conversation_not_found")
    messages = await repository.history(conversation_id, user_id, limit=100)
    return [
        MessageResponse(
            id=item.id,
            role=item.role,
            content=item.content,
            citations=item.citations or [],
            created_at=item.created_at,
        )
        for item in messages
    ]


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: UUID,
    user_id: UUID = Depends(get_current_user),
    _csrf: None = Depends(require_csrf_token),
    db: AsyncSession = Depends(get_db),
) -> None:
    if not await ChatService(db).conversations.delete_owned(conversation_id, user_id):
        raise ValidationError("Conversation not found", "conversation_not_found")
    await db.commit()
