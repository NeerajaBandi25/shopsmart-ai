"""Grounded chat orchestration with bounded history and citations."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import AuthorizationError, ValidationError
from src.core.observability import metrics
from src.models.ai import ChatMessage
from src.schemas.ai import Citation
from src.services.ai_provider import GroundedAnswerProvider
from src.services.ai_repository import ConversationRepository
from src.services.ai_retrieval import RetrievalService


class ChatService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.retrieval = RetrievalService(db)
        self.provider = GroundedAnswerProvider()
        self.conversations = ConversationRepository(db)

    async def answer(self, owner_id: UUID, question: str, conversation_id: UUID | None = None) -> dict:
        question = question.strip()
        if not question:
            raise ValidationError("Question is required", "empty_question")
        conversation = await self.conversations.get_owned(conversation_id, owner_id) if conversation_id else None
        if conversation_id and not conversation:
            raise AuthorizationError("Conversation not found", "conversation_not_found")
        if not conversation:
            conversation = await self.conversations.create(owner_id, question[:80])
        retrieved = await self.retrieval.retrieve(owner_id, question)
        metrics.record_ai_event("ai_retrieval")
        evidence = self.retrieval.evidence(retrieved)
        result = self.provider.answer(question, evidence)
        if not result.answerable:
            metrics.record_ai_event("ai_no_answer")
        used_ids = set(result.evidence_ids)
        citations = [Citation(citation_id=f"source-{index + 1}", document_id=UUID(str(item.chunk.document_id)), source_label=item.chunk.source_label, page_number=item.chunk.page_number, chunk_index=item.chunk.chunk_index) for index, item in enumerate(retrieved) if str(item.chunk.id) in used_ids] if result.answerable else []
        citation_dicts = [citation.model_dump(mode="json") for citation in citations]
        await self.conversations.add_message(conversation.id, owner_id, "user", question, token_count=len(question.split()))
        await self.conversations.add_message(conversation.id, owner_id, "assistant", result.answer, citations=citation_dicts, token_count=result.token_count)
        await self.db.commit()
        return {"conversation_id": conversation.id, "answer": result.answer, "answerable": result.answerable, "citations": citations, "retrieval_count": len(retrieved), "token_count": result.token_count, "estimated_cost_usd": 0.0}
