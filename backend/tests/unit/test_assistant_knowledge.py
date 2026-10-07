import json
from pathlib import Path
from uuid import uuid4

import pytest

from src.models.user import User
from src.services.ai_ingestion import DocumentIngestionService
from src.services.assistant_knowledge import (
    KnowledgeIngestionService,
    KnowledgeRetrievalService,
)

LOCAL_POLICY_CORPUS = (
    Path(__file__).parents[2] / "evals" / "datasets" / "local_shopsmart_knowledge_v1.json"
)


@pytest.mark.asyncio
async def test_local_fictional_policy_corpus_produces_grounded_answer_and_active_citation(
    test_db, monkeypatch
):
    from src.core.config import settings
    from src.services.commerce_assistant import CommerceAssistantService

    monkeypatch.setattr(settings, "ai_provider", "deterministic")
    corpus = json.loads(LOCAL_POLICY_CORPUS.read_text(encoding="utf-8"))
    assert corpus["version"] == "local-shopsmart-knowledge-v1"
    assert "Fictional, locally authored" in corpus["notice"]

    ingestion = KnowledgeIngestionService(test_db)
    for source in corpus["sources"]:
        await ingestion.publish(**source)

    owner = User(email=f"{uuid4()}@example.com", password_hash="test-hash")
    test_db.add(owner)
    await test_db.commit()

    returns_key = "local-demo-v1-returns"
    question = "Within how many calendar days after delivery may an eligible item be returned?"
    matches = await KnowledgeRetrievalService(test_db).retrieve(
        question,
        source_keys={returns_key},
    )
    citations = KnowledgeRetrievalService.evidence(matches)
    result = await CommerceAssistantService(test_db).answer(owner.id, question)

    assert matches
    assert "30 calendar days" in matches[0].chunk.text
    assert citations
    assert citations[0].chunk_id == str(matches[0].chunk.id)
    assert citations[0].source_label == "Local Demo Returns Guide"
    assert citations[0].classification == "PUBLIC"
    assert result["answerable"] is True
    assert "30 calendar days" in result["answer"]
    assert result["citations"][0].knowledge_version_id == matches[0].chunk.version_id


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


@pytest.mark.asyncio
async def test_public_provider_retrieval_requires_explicit_source_key_allowlist(test_db):
    service = KnowledgeIngestionService(test_db)
    approved = await service.publish(
        "approved-policy", "Approved policy", "returns", "Approved return policy terms."
    )
    await service.publish(
        "local-eval-only", "Synthetic local evaluation", "returns", "Synthetic policy terms."
    )

    matches = await KnowledgeRetrievalService(test_db).retrieve(
        "policy terms", source_keys={"approved-policy"}
    )
    blocked = await KnowledgeRetrievalService(test_db).retrieve("policy terms", source_keys=set())

    assert matches
    assert all(item.source_id == approved for item in matches)
    assert blocked == []
