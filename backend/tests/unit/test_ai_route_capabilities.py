import pytest

from src.api.v1 import ai_routes
from src.core.exceptions import AuthorizationError


def test_customer_document_capability_is_disabled_by_default(monkeypatch):
    monkeypatch.setattr(ai_routes.settings, "ai_user_documents_enabled", False)

    with pytest.raises(AuthorizationError, match="Customer document ingestion is disabled"):
        ai_routes.require_internal_document_capability()


def test_customer_document_capability_can_be_enabled_for_internal_tests(monkeypatch):
    monkeypatch.setattr(ai_routes.settings, "ai_user_documents_enabled", True)

    assert ai_routes.require_internal_document_capability() is None
