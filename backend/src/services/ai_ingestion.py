"""Document normalization, chunking, and deterministic ingestion."""

import hashlib
import re
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import ValidationError
from src.models.ai import Document, DocumentChunk, DocumentVersion
from src.services.ai_provider import EmbeddingProvider


@dataclass(frozen=True)
class ChunkDraft:
    text: str
    index: int
    content_hash: str
    source_label: str
    page_number: int | None


def normalize_text(content: str) -> str:
    return re.sub(r"\s+", " ", content.replace("\x00", "")).strip()


def extract_document_text(content: bytes, content_type: str) -> str:
    """Extract text from bounded plain text or text-bearing PDF bytes."""
    if content_type == "text/plain":
            try:
                return normalize_text(content.decode("utf-8"))
            except UnicodeDecodeError as exc:
                raise ValidationError("Document text is not valid UTF-8", "malformed_document") from exc
    if content_type == "application/pdf":
        if not content.startswith(b"%PDF"):
            raise ValidationError("Malformed PDF document", "malformed_document")
        decoded = content.decode("latin-1", errors="ignore")
        streams = re.findall(r"stream\s*(.*?)\s*endstream", decoded, flags=re.DOTALL)
        return normalize_text(" ".join(streams) or decoded)
    raise ValidationError("Unsupported document type", "unsupported_document_type")


def chunk_text(content: str, source_label: str, size: int = 900, overlap: int = 120) -> list[ChunkDraft]:
    normalized = normalize_text(content)
    if not normalized:
        return []
    words = normalized.split()
    drafts: list[ChunkDraft] = []
    start = 0
    index = 0
    while start < len(words):
        end = min(len(words), start + size // 5)
        text = " ".join(words[start:end]).strip()
        if text:
            drafts.append(ChunkDraft(text, index, hashlib.sha256(text.encode()).hexdigest(), source_label, None))
            index += 1
        if end == len(words):
            break
        start = max(start + 1, end - overlap // 5)
    return drafts


class DocumentIngestionService:
    def __init__(self, db: AsyncSession, embedder: EmbeddingProvider | None = None) -> None:
        self.db = db
        self.embedder = embedder or EmbeddingProvider()

    async def ingest(self, owner_id: UUID, title: str, source_name: str, content: str) -> Document:
        normalized = normalize_text(content)
        if not normalized:
            raise ValidationError("Document is empty", "empty_document")
        if len(normalized) > 2_000_000:
            raise ValidationError("Document exceeds the maximum size", "document_too_large")
        content_hash = hashlib.sha256(normalized.encode()).hexdigest()
        existing = await self.db.scalar(select(Document).where(Document.owner_id == owner_id, Document.content_hash == content_hash))
        if existing:
            return existing
        existing = await self.db.scalar(select(Document).where(Document.owner_id == owner_id, Document.title == title.strip(), Document.source_name == source_name.strip()))
        if existing:
            existing.content_hash = content_hash
        drafts = chunk_text(normalized, source_name)
        if not drafts:
            raise ValidationError("Document produced no usable text", "empty_document")
        document = existing or Document(owner_id=owner_id, title=title.strip(), source_name=source_name.strip(), content_hash=content_hash)
        if not existing:
            self.db.add(document)
            await self.db.flush()
        version_number = (await self.db.scalar(select(func.count(DocumentVersion.id)).where(DocumentVersion.document_id == document.id)) or 0) + 1
        version = DocumentVersion(document_id=document.id, version_number=version_number, status="processing", extracted_text=normalized)
        self.db.add(version)
        await self.db.flush()
        try:
            for draft in drafts:
                self.db.add(DocumentChunk(document_id=document.id, version_id=version.id, chunk_index=draft.index, text=draft.text, content_hash=draft.content_hash, source_label=draft.source_label, page_number=draft.page_number, embedding=self.embedder.embed(draft.text)))
            version.status = "ready"
            document.active_version_id = version.id
            await self.db.commit()
            await self.db.refresh(document)
            return document
        except Exception as exc:
            version.status = "failed"
            version.retry_count += 1
            version.failure_reason = type(exc).__name__[:255]
            await self.db.commit()
            raise ValidationError("Document indexing failed", "embedding_failed") from exc
