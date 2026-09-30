"""Owner-filtered retrieval over the derived embedding data."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.ai import Document, DocumentChunk
from src.services.ai_provider import EmbeddingProvider, Evidence


@dataclass(frozen=True)
class RetrievedChunk:
    chunk: DocumentChunk
    score: float
    classification: str = "PRIVATE"


def cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right)) / (
        (sum(a * a for a in left) ** 0.5 or 1) * (sum(b * b for b in right) ** 0.5 or 1)
    )


class RetrievalService:
    def __init__(self, db: AsyncSession, embedder: EmbeddingProvider | None = None) -> None:
        self.db = db
        self.embedder = embedder or EmbeddingProvider()

    async def retrieve(
        self, owner_id: UUID, question: str, top_k: int = 5, threshold: float = 0.12
    ) -> list[RetrievedChunk]:
        query_embedding = self.embedder.embed(question)
        rows = (
            await self.db.execute(
                select(DocumentChunk, Document.classification)
                .join(Document, Document.id == DocumentChunk.document_id)
                .where(
                    Document.owner_id == owner_id,
                    Document.active_version_id == DocumentChunk.version_id,
                )
            )
        ).all()
        ranked = sorted(
            (
                RetrievedChunk(row, cosine(query_embedding, row.embedding), classification)
                for row, classification in rows
            ),
            key=lambda item: item.score,
            reverse=True,
        )
        result: list[RetrievedChunk] = []
        seen: set[str] = set()
        for item in ranked:
            if item.score < threshold or item.chunk.content_hash in seen:
                continue
            seen.add(item.chunk.content_hash)
            result.append(item)
            if len(result) >= min(max(top_k, 1), 10):
                break
        return result

    @staticmethod
    def evidence(items: list[RetrievedChunk]) -> list[Evidence]:
        return [
            Evidence(
                str(item.chunk.id),
                item.chunk.text,
                item.chunk.source_label,
                item.chunk.page_number,
                item.chunk.chunk_index,
                item.classification,
            )
            for item in items
        ]
