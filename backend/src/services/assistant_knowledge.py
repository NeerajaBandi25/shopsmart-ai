"""Server-owned, versioned ShopSmart knowledge ingestion and retrieval."""

import hashlib
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import ValidationError
from src.models.ai import KnowledgeChunk, KnowledgeSource, KnowledgeVersion
from src.services.ai_ingestion import chunk_text, normalize_text
from src.services.ai_provider import EmbeddingProvider, Evidence
from src.services.ai_retrieval import cosine


@dataclass(frozen=True)
class RetrievedKnowledge:
    source_id: UUID
    chunk: KnowledgeChunk
    score: float


class KnowledgeIngestionService:
    """Publish curated knowledge from trusted server-side callers only."""

    def __init__(self, db: AsyncSession, embedder: EmbeddingProvider | None = None) -> None:
        self.db = db
        self.embedder = embedder or EmbeddingProvider()

    async def publish(self, source_key: str, title: str, category: str, content: str) -> UUID:
        normalized = normalize_text(content)
        if not normalized or len(normalized) > 2_000_000:
            raise ValidationError(
                "Knowledge content is empty or too large", "invalid_knowledge_content"
            )
        content_hash = hashlib.sha256(normalized.encode()).hexdigest()
        source = await self.db.scalar(
            select(KnowledgeSource).where(KnowledgeSource.source_key == source_key)
        )
        if source and source.active_version_id:
            active = await self.db.get(KnowledgeVersion, source.active_version_id)
            if active and active.content_hash == content_hash:
                return source.id
        if source is None:
            source = KnowledgeSource(
                source_key=source_key[:100], title=title[:255], category=category[:64]
            )
            self.db.add(source)
            await self.db.flush()
        else:
            source.title = title[:255]
            source.category = category[:64]
            source.is_active = True

        version_number = (
            await self.db.scalar(
                select(func.max(KnowledgeVersion.version_number)).where(
                    KnowledgeVersion.source_id == source.id
                )
            )
            or 0
        ) + 1
        version = KnowledgeVersion(
            source_id=source.id,
            version_number=version_number,
            content_hash=content_hash,
            status="ready",
        )
        self.db.add(version)
        await self.db.flush()
        drafts = chunk_text(normalized, title)
        for draft in drafts:
            self.db.add(
                KnowledgeChunk(
                    version_id=version.id,
                    chunk_index=draft.index,
                    text=draft.text,
                    content_hash=draft.content_hash,
                    source_label=draft.source_label,
                    page_number=draft.page_number,
                    embedding=self.embedder.embed(draft.text),
                )
            )
        source.active_version_id = version.id
        await self.db.commit()
        return source.id


class KnowledgeRetrievalService:
    def __init__(self, db: AsyncSession, embedder: EmbeddingProvider | None = None) -> None:
        self.db = db
        self.embedder = embedder or EmbeddingProvider()

    async def retrieve(
        self,
        question: str,
        top_k: int = 5,
        threshold: float = 0.12,
        source_keys: set[str] | None = None,
    ) -> list[RetrievedKnowledge]:
        if source_keys is not None and not source_keys:
            return []
        statement = (
            select(KnowledgeSource.id, KnowledgeChunk)
            .join(KnowledgeVersion, KnowledgeVersion.id == KnowledgeChunk.version_id)
            .join(KnowledgeSource, KnowledgeSource.id == KnowledgeVersion.source_id)
            .where(
                KnowledgeSource.is_active.is_(True),
                KnowledgeSource.active_version_id == KnowledgeVersion.id,
                KnowledgeVersion.status == "ready",
            )
        )
        if source_keys is not None:
            statement = statement.where(KnowledgeSource.source_key.in_(source_keys))
        rows = (await self.db.execute(statement)).all()
        query_embedding = self.embedder.embed(question)
        ranked = sorted(
            (
                RetrievedKnowledge(source_id, chunk, cosine(query_embedding, chunk.embedding))
                for source_id, chunk in rows
            ),
            key=lambda item: item.score,
            reverse=True,
        )
        result: list[RetrievedKnowledge] = []
        for item in ranked:
            if item.score >= threshold:
                result.append(item)
            if len(result) >= min(max(top_k, 1), 10):
                break
        return result

    @staticmethod
    def evidence(items: list[RetrievedKnowledge]) -> list[Evidence]:
        return [
            Evidence(
                chunk_id=str(item.chunk.id),
                text=item.chunk.text,
                source_label=item.chunk.source_label,
                page_number=item.chunk.page_number,
                chunk_index=item.chunk.chunk_index,
                classification="PUBLIC",
            )
            for item in items
        ]
