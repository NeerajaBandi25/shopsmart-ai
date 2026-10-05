"""Strict argument validation and owner/context boundaries for LLM-selected tools."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.services.assistant_tools import (
    MAX_TOOL_STEPS,
    CommerceToolExecutor,
    SearchProductsArgs,
    ToolCallError,
    tool_schemas,
)


def test_tool_schemas_are_explicit_and_exclude_private_tools_by_default():
    public_names = {item["function"]["name"] for item in tool_schemas(include_private=False)}
    all_names = {item["function"]["name"] for item in tool_schemas()}
    approved_names = {
        item["function"]["name"]
        for item in tool_schemas(include_private=False, include_knowledge=True)
    }

    assert public_names == {
        "search_products",
        "get_product_details",
        "compare_products",
    }
    assert {"get_cart", "add_to_cart", "get_orders", "get_order_status"}.issubset(all_names)
    assert "retrieve_policy_knowledge" not in all_names
    assert "retrieve_policy_knowledge" in approved_names
    assert MAX_TOOL_STEPS == 5


def test_search_tool_rejects_unknown_fields_and_invalid_price_ranges():
    with pytest.raises(ValidationError):
        SearchProductsArgs.model_validate({"query": "laptop", "user_id": str(uuid4())})
    with pytest.raises(ValidationError):
        SearchProductsArgs.model_validate(
            {"category": "laptops", "min_price_cents": 5000, "max_price_cents": 1000}
        )
    with pytest.raises(ValidationError):
        SearchProductsArgs.model_validate({"category": "unrestricted_sql"})


@pytest.mark.asyncio
async def test_product_reference_must_be_in_the_current_authorized_result_set():
    executor = CommerceToolExecutor.__new__(CommerceToolExecutor)
    executor.conversation = type("Conversation", (), {"context": {"product_ids": []}})()

    with pytest.raises(ToolCallError, match="authorized search results"):
        await executor._authorized_product(uuid4())


@pytest.mark.asyncio
async def test_policy_tool_is_blocked_without_external_source_allowlist():
    executor = CommerceToolExecutor.__new__(CommerceToolExecutor)
    executor.public_knowledge_source_keys = set()

    with pytest.raises(ToolCallError, match="No externally approved"):
        await executor.execute("retrieve_policy_knowledge", {"question": "returns"})
