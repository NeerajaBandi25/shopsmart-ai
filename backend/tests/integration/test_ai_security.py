from uuid import uuid4

import pytest

from src.services.ai_ingestion import DocumentIngestionService
from src.services.ai_retrieval import RetrievalService


@pytest.mark.asyncio
async def test_retrieval_isolated_by_owner(test_db):
    owner_a = uuid4()
    owner_b = uuid4()
    await DocumentIngestionService(test_db).ingest(owner_a, "A", "a.txt", "private alpha return policy")
    await DocumentIngestionService(test_db).ingest(owner_b, "B", "b.txt", "private beta warranty policy")

    a_results = await RetrievalService(test_db).retrieve(owner_a, "alpha return")
    b_results = await RetrievalService(test_db).retrieve(owner_b, "alpha return")

    assert a_results
    assert all(result.chunk.source_label == "a.txt" for result in a_results)
    assert b_results == []


@pytest.mark.asyncio
async def test_duplicate_content_is_idempotent(test_db):
    owner = uuid4()
    first = await DocumentIngestionService(test_db).ingest(owner, "Policy", "policy.txt", "same content")
    second = await DocumentIngestionService(test_db).ingest(owner, "Policy copy", "copy.txt", "same content")
    assert first.id == second.id
