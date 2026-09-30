"""Owner-scoped conversation persistence."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.ai import ChatMessage, Conversation


class ConversationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_owned(self, conversation_id: UUID, owner_id: UUID) -> Conversation | None:
        return await self.db.scalar(select(Conversation).where(Conversation.id == conversation_id, Conversation.owner_id == owner_id))

    async def create(self, owner_id: UUID, title: str = "New conversation") -> Conversation:
        conversation = Conversation(owner_id=owner_id, title=title[:255])
        self.db.add(conversation)
        await self.db.flush()
        return conversation

    async def list_owned(self, owner_id: UUID, limit: int = 50) -> list[Conversation]:
        result = await self.db.execute(select(Conversation).where(Conversation.owner_id == owner_id).order_by(Conversation.created_at.desc()).limit(limit))
        return list(result.scalars().all())

    async def delete_owned(self, conversation_id: UUID, owner_id: UUID) -> bool:
        conversation = await self.get_owned(conversation_id, owner_id)
        if not conversation:
            return False
        await self.db.delete(conversation)
        await self.db.flush()
        return True

    async def history(self, conversation_id: UUID, owner_id: UUID, limit: int = 8) -> list[ChatMessage]:
        result = await self.db.execute(select(ChatMessage).join(Conversation, Conversation.id == ChatMessage.conversation_id).where(ChatMessage.conversation_id == conversation_id, Conversation.owner_id == owner_id).order_by(ChatMessage.created_at.desc()).limit(limit))
        return list(reversed(result.scalars().all()))

    async def add_message(self, conversation_id: UUID, owner_id: UUID, role: str, content: str, citations: list[dict] | None = None, token_count: int = 0) -> ChatMessage:
        if not await self.get_owned(conversation_id, owner_id):
            raise ValueError("conversation ownership check failed")
        message = ChatMessage(conversation_id=conversation_id, role=role, content=content[:12000], citations=citations, token_count=token_count)
        self.db.add(message)
        await self.db.flush()
        return message
