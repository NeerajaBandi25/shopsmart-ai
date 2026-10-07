"""Owner-scoped conversation persistence."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.ai import ChatMessage, Conversation


class ConversationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_owned(self, conversation_id: UUID, owner_id: UUID) -> Conversation | None:
        return await self.db.scalar(
            select(Conversation).where(
                Conversation.id == conversation_id, Conversation.owner_id == owner_id
            )
        )

    async def create(self, owner_id: UUID, title: str = "New conversation") -> Conversation:
        conversation = Conversation(owner_id=owner_id, title=title[:255])
        self.db.add(conversation)
        await self.db.flush()
        return conversation

    async def list_owned(self, owner_id: UUID, limit: int = 50) -> list[Conversation]:
        result = await self.db.execute(
            select(Conversation)
            .where(Conversation.owner_id == owner_id)
            .order_by(Conversation.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def delete_owned(self, conversation_id: UUID, owner_id: UUID) -> bool:
        conversation = await self.get_owned(conversation_id, owner_id)
        if not conversation:
            return False
        await self.db.delete(conversation)
        await self.db.flush()
        return True

    async def history(
        self, conversation_id: UUID, owner_id: UUID, limit: int = 8
    ) -> list[ChatMessage]:
        result = await self.db.execute(
            select(ChatMessage)
            .join(Conversation, Conversation.id == ChatMessage.conversation_id)
            .where(
                ChatMessage.conversation_id == conversation_id, Conversation.owner_id == owner_id
            )
            .order_by(ChatMessage.sequence.desc())
            .limit(limit)
        )
        return list(reversed(result.scalars().all()))

    async def request_replay(
        self, owner_id: UUID, client_request_id: UUID
    ) -> tuple[ChatMessage, ChatMessage | None] | None:
        user_message = await self.db.scalar(
            select(ChatMessage).where(
                ChatMessage.client_request_owner_id == owner_id,
                ChatMessage.client_request_id == client_request_id,
                ChatMessage.role == "user",
            )
        )
        if user_message is None:
            return None
        response = await self.db.scalar(
            select(ChatMessage).where(
                ChatMessage.conversation_id == user_message.conversation_id,
                ChatMessage.sequence == user_message.sequence + 1,
                ChatMessage.role == "assistant",
            )
        )
        return user_message, response

    async def add_message(
        self,
        conversation_id: UUID,
        owner_id: UUID,
        role: str,
        content: str,
        citations: list[dict] | None = None,
        result_data: dict | None = None,
        token_count: int = 0,
        client_request_id: UUID | None = None,
        client_request_conversation_id: UUID | None = None,
    ) -> ChatMessage:
        conversation = await self.db.scalar(
            select(Conversation)
            .where(Conversation.id == conversation_id, Conversation.owner_id == owner_id)
            .with_for_update()
        )
        if not conversation:
            raise ValueError("conversation ownership check failed")
        latest_sequence = await self.db.scalar(
            select(func.max(ChatMessage.sequence)).where(
                ChatMessage.conversation_id == conversation_id
            )
        )
        message = ChatMessage(
            conversation_id=conversation_id,
            sequence=(latest_sequence or 0) + 1,
            role=role,
            content=content[:12000],
            citations=citations,
            result_data=result_data,
            token_count=token_count,
            client_request_id=client_request_id,
            client_request_owner_id=owner_id if client_request_id is not None else None,
            client_request_conversation_id=(
                client_request_conversation_id if client_request_id is not None else None
            ),
        )
        self.db.add(message)
        await self.db.flush()
        return message
