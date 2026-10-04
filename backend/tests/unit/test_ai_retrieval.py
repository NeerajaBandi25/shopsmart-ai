import pytest

from src.models.ai import Document, DocumentChunk
from src.services.ai_retrieval import cosine


def test_cosine_similarity_is_bounded():
    assert cosine([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_owner_scoped_model_has_explicit_owner_field():
    assert "owner_id" in Document.__table__.columns
    assert "document_id" in DocumentChunk.__table__.columns
