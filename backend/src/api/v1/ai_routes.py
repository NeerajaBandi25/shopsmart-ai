"""Authenticated document assistant API."""

import asyncio
import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.deps import get_current_user, get_db, require_csrf_token
from src.core.config import settings
from src.core.exceptions import AuthorizationError, ConflictError, NotFoundError, ValidationError
from src.core.observability import request_id_context
from src.models.ai import ChatMessage, Conversation, Document, DocumentChunk
from src.models.user import User
from src.schemas.ai import (
    ChatRequest,
    ChatResponse,
    ConversationResponse,
    DocumentResponse,
    DocumentTextRequest,
    MessageResponse,
)
from src.services.ai_ingestion import DocumentIngestionService, extract_document_text
from src.services.ai_repository import ConversationRepository
from src.services.commerce_assistant import CommerceAssistantService
from src.services.shopper_preferences import ExplicitPreferences, ShopperPreferenceService

router = APIRouter(prefix="/ai", tags=["AI assistant"])
logger = logging.getLogger(__name__)


async def _answer_idempotently(
    db: AsyncSession,
    user_id: UUID,
    request: ChatRequest,
    *,
    stream_events=None,
) -> dict:
    # Serialize assistant submissions per owner until the request-keyed user message
    # and its authoritative response commit together.
    await db.scalar(select(User.id).where(User.id == user_id).with_for_update())
    conversations = ConversationRepository(db)
    replay = await conversations.request_replay(user_id, request.request_id)
    if replay:
        prior_request, prior_response = replay
        if prior_request.content != request.question or (
            request.conversation_id != prior_request.client_request_conversation_id
        ):
            raise ConflictError(
                "This assistant request key was already used for a different message.",
                "idempotency_conflict",
            )
        if prior_response is None:
            raise ConflictError(
                "This assistant request is still being processed.", "request_in_progress"
            )
        result_data = prior_response.result_data or {}
        return {
            "conversation_id": prior_response.conversation_id,
            "message_id": prior_response.id,
            "answer": prior_response.content,
            "answerable": True,
            "reason": None,
            "citations": prior_response.citations or [],
            "intent": result_data.get("intent", "UNSUPPORTED"),
            "result_data": result_data,
            "tool_events": [],
            "usage": result_data.get("usage"),
            "degraded_mode": False,
            "trace": result_data.get("trace"),
        }
    return await CommerceAssistantService(db).answer(
        user_id,
        request.question,
        request.conversation_id,
        stream_events=stream_events,
        client_request_id=request.request_id,
    )


@router.get("/preferences")
async def get_preferences(
    user_id: UUID = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    return await ShopperPreferenceService(db).get(user_id)


@router.put("/preferences")
async def replace_preferences(
    preferences: ExplicitPreferences,
    user_id: UUID = Depends(get_current_user),
    _csrf: None = Depends(require_csrf_token),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await ShopperPreferenceService(db).replace(user_id, preferences)


@router.delete("/preferences", status_code=204)
async def clear_preferences(
    user_id: UUID = Depends(get_current_user),
    _csrf: None = Depends(require_csrf_token),
    db: AsyncSession = Depends(get_db),
) -> None:
    await ShopperPreferenceService(db).clear(user_id)


def require_internal_document_capability() -> None:
    allowed_environments = {"local", "dev", "development", "test"}
    app_env = settings.app_env.strip().lower()
    if not settings.ai_user_documents_enabled or app_env not in allowed_environments:
        raise AuthorizationError(
            "Customer document ingestion is disabled", "document_ingestion_disabled"
        )


async def _ingest(
    user_id: UUID, title: str, source_name: str, content: str, db: AsyncSession
) -> DocumentResponse:
    document = await DocumentIngestionService(db).ingest(user_id, title, source_name, content)
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


@router.post(
    "/documents", response_model=DocumentResponse, status_code=201, include_in_schema=False
)
async def ingest_document(
    request: DocumentTextRequest,
    user_id: UUID = Depends(get_current_user),
    _csrf: None = Depends(require_csrf_token),
    _internal: None = Depends(require_internal_document_capability),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    return await _ingest(user_id, request.title, request.source_name, request.content, db)


@router.post(
    "/documents/upload", response_model=DocumentResponse, status_code=201, include_in_schema=False
)
async def upload_document(
    request: Request,
    title: str = Query(min_length=1, max_length=255),
    source_name: str = Query(min_length=1, max_length=255),
    user_id: UUID = Depends(get_current_user),
    _csrf: None = Depends(require_csrf_token),
    _internal: None = Depends(require_internal_document_capability),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
    body = await request.body()
    if len(body) > 2_500_000:
        raise ValidationError("Document exceeds the maximum size", "document_too_large")
    return await _ingest(user_id, title, source_name, extract_document_text(body, content_type), db)


@router.get("/documents", response_model=list[DocumentResponse], include_in_schema=False)
async def list_documents(
    user_id: UUID = Depends(get_current_user),
    _internal: None = Depends(require_internal_document_capability),
    db: AsyncSession = Depends(get_db),
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
    return ChatResponse(**await _answer_idempotently(db, user_id, request))


@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    user_id: UUID = Depends(get_current_user),
    _csrf: None = Depends(require_csrf_token),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Stream safe status and verified final content; never expose model reasoning."""

    async def events():
        queue: asyncio.Queue[tuple[str, dict] | None] = asyncio.Queue()

        async def publish(event_name: str, data: dict) -> None:
            await queue.put((event_name, data))

        async def run_assistant() -> None:
            try:
                result = await _answer_idempotently(db, user_id, request, stream_events=publish)
                # Stream only after authoritative services and policy checks have completed.
                answer = str(result.get("answer") or "")
                for offset in range(0, len(answer), 48):
                    await publish("assistant.delta", {"text": answer[offset : offset + 48]})
                await publish("assistant.completed", jsonable_encoder(result))
            except Exception as exc:
                # Avoid leaking provider responses, tool payloads, or exception text to clients.
                logger.error(
                    "assistant_stream_failed",
                    extra={
                        "request_id": request_id_context.get(),
                        "exception_type": type(exc).__name__,
                    },
                )
                await publish(
                    "assistant.error",
                    {"message": "The assistant could not complete this request. Please try again."},
                )
            finally:
                await queue.put(None)

        def encode(event_name: str, data: dict) -> bytes:
            return f"event: {event_name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode()

        yield encode("assistant.started", {"status": "started"})
        task = asyncio.create_task(run_assistant())
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield encode(*item)
        finally:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )


@router.get("/usage")
async def assistant_usage(
    user_id: UUID = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    """Return an owner-scoped aggregate over the most recent 2,000 chat messages."""
    rows = (
        await db.scalars(
            select(ChatMessage)
            .join(Conversation, Conversation.id == ChatMessage.conversation_id)
            .where(Conversation.owner_id == user_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(2000)
        )
    ).all()
    input_tokens = sum(item.token_count for item in rows if item.role == "user")
    output_tokens = sum(item.token_count for item in rows if item.role == "assistant")
    providers: dict[str, dict] = {}
    estimated_cost_usd = 0.0
    has_cost = False
    request_count = 0
    tool_calls = 0
    for item in rows:
        usage = ((item.result_data or {}).get("usage") or {}) if item.role == "assistant" else {}
        if not usage:
            continue
        request_count += 1
        tool_calls += int(usage.get("tool_calls", 0) or 0)
        provider = str(usage.get("provider", "unknown"))
        model = str(usage.get("model", "unknown"))
        key = f"{provider}:{model}"
        current = providers.setdefault(key, {"requests": 0, "input_tokens": 0, "output_tokens": 0})
        current["requests"] += 1
        current["input_tokens"] += int(usage.get("input_tokens", 0) or 0)
        current["output_tokens"] += int(usage.get("output_tokens", 0) or 0)
        cost = usage.get("estimated_cost_usd")
        if cost is not None:
            estimated_cost_usd += float(cost)
            has_cost = True
    return {
        "message_window": len(rows),
        "requests": request_count,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "tool_calls": tool_calls,
        "estimated_cost_usd": round(estimated_cost_usd, 8) if has_cost else None,
        "by_provider_model": providers,
    }


@router.get("/conversations", response_model=list[ConversationResponse])
async def list_conversations(
    user_id: UUID = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[ConversationResponse]:
    return [
        ConversationResponse(id=item.id, title=item.title, created_at=item.created_at)
        for item in await ConversationRepository(db).list_owned(user_id)
    ]


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageResponse])
async def conversation_messages(
    conversation_id: UUID,
    user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MessageResponse]:
    repository = ConversationRepository(db)
    if not await repository.get_owned(conversation_id, user_id):
        raise NotFoundError("Conversation not found", "conversation_not_found")
    messages = await repository.history(conversation_id, user_id, limit=100)
    return [
        MessageResponse(
            id=item.id,
            role=item.role,
            content=item.content,
            citations=item.citations or [],
            result_data=item.result_data,
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
    if not await ConversationRepository(db).delete_owned(conversation_id, user_id):
        raise NotFoundError("Conversation not found", "conversation_not_found")
    await db.commit()
