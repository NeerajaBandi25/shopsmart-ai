from uuid import uuid4

import pytest

from src.models.user import User
from src.services.ai_ingestion import DocumentIngestionService
from src.services.assistant_knowledge import (
    KnowledgeIngestionService,
    KnowledgeRetrievalService,
)


@pytest.mark.asyncio
async def test_policy_retrieval_uses_only_server_owned_knowledge(test_db):
    user = User(email=f"{uuid4()}@example.com", password_hash="test-hash")
    test_db.add(user)
    await test_db.commit()
    await DocumentIngestionService(test_db).ingest(
        user.id,
        "Customer upload",
        "customer.txt",
        "Returns are never allowed for any item.",
    )
    source_id = await KnowledgeIngestionService(test_db).publish(
        "returns-policy",
        "Returns policy",
        "returns",
        "Customers may return eligible purchases within the stated return period.",
    )

    matches = await KnowledgeRetrievalService(test_db).retrieve("return eligible purchases")

    assert matches
    assert all(item.source_id == source_id for item in matches)
    assert all("never allowed" not in item.chunk.text for item in matches)
    assert all(
        item.classification == "PUBLIC" for item in KnowledgeRetrievalService.evidence(matches)
    )


@pytest.mark.asyncio
async def test_policy_retrieval_returns_no_evidence_when_corpus_is_empty(test_db):
    matches = await KnowledgeRetrievalService(test_db).retrieve("warranty terms")

    assert matches == []
