import json
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.core.exceptions import AppException, NotFoundError
from src.core.observability import JsonLogFormatter
from src.services import commerce_assistant as assistant_module
from src.services.adaptive_model_router import ModelSelection
from src.services.ai_gateway import FunctionCall, ProviderUnavailable, ToolTurn
from src.services.ai_governance import PolicyViolation
from src.services.ai_provider import Evidence, ProviderAnswer
from src.services.assistant_router import AssistantIntent
from src.services.commerce_assistant import CommerceAssistantService, _tools_for_intent


def test_llm_tools_are_scoped_to_route_and_private_data_policy():
    public_search_tools = _tools_for_intent(
        AssistantIntent.PRODUCT_SEARCH,
        allow_private=False,
        knowledge_available=True,
    )
    private_cart_tools = _tools_for_intent(
        AssistantIntent.CART_QUERY,
        allow_private=True,
        knowledge_available=True,
    )
    cart_action_tools = _tools_for_intent(
        AssistantIntent.CART_ACTION,
        allow_private=True,
        knowledge_available=False,
    )
    coupon_tools = _tools_for_intent(
        AssistantIntent.COUPON_APPLY,
        allow_private=True,
        knowledge_available=False,
    )

    assert "search_products" in public_search_tools
    assert "retrieve_policy_knowledge" not in public_search_tools
    assert "get_cart" not in public_search_tools
    assert "apply_promotion" not in public_search_tools
    assert private_cart_tools == {"get_cart"}
    assert {"add_to_cart", "remove_from_cart"} <= cart_action_tools
    assert "get_orders" not in cart_action_tools
    assert "apply_promotion" in coupon_tools
    assert "remove_promotion" not in coupon_tools


class FakeConversations:
    def __init__(self, _db):
        self.conversation = SimpleNamespace(id=uuid4(), context={})
        self.messages = []

    async def get_owned(self, conversation_id, owner_id):
        return self.conversation if conversation_id == self.conversation.id else None

    async def create(self, owner_id, title):
        return self.conversation

    async def add_message(self, *args, **kwargs):
        self.messages.append((args, kwargs))
        return SimpleNamespace(id=uuid4())

    async def history(self, *_args, **_kwargs):
        return []


class FakeProducts:
    def __init__(self, _db):
        self.search = AsyncMock(return_value=[])
        self.get = AsyncMock(return_value=None)

    async def search_products(self, *args, **kwargs):
        return await self.search(*args, **kwargs)

    async def get_product(self, product_id):
        return await self.get(product_id)


class FakeCart:
    def __init__(self, _db):
        self.get_cart = AsyncMock(return_value={"items": [], "subtotal": 0, "currency": "INR"})
        self.add_item = AsyncMock(return_value={"items": [], "subtotal": 0, "currency": "INR"})
        self.remove_item = AsyncMock(return_value={"items": [], "subtotal": 0, "currency": "INR"})
        self.get_available_promotions = AsyncMock(return_value=[])
        self.check_coupon = AsyncMock(
            return_value={
                "coupon_evaluation": {
                    "eligible": False,
                    "reason_code": "unknown_or_ineligible",
                    "discount_cents": 0,
                },
                "applied_promotions": [],
                "items": [],
                "subtotal": 0,
                "total_cents": 0,
            }
        )
        self.apply_coupon = AsyncMock(return_value={"items": [], "subtotal": 0})
        self.remove_coupon = AsyncMock(return_value={"items": [], "subtotal": 0})


class FakeOrders:
    def __init__(self, _db):
        self.get_user_orders = AsyncMock(return_value=[])


class FakeKnowledge:
    def __init__(self, _db):
        self.retrieve = AsyncMock(return_value=[])

    @staticmethod
    def evidence(items):
        return [
            Evidence(
                str(item.chunk.id),
                item.chunk.text,
                item.chunk.source_label,
                item.chunk.page_number,
                item.chunk.chunk_index,
                "PUBLIC",
            )
            for item in items
        ]


class FakeGateway:
    def __init__(self):
        self.answer = AsyncMock()
        self.select_model = AsyncMock()
        self.tool_turn = AsyncMock()


@pytest.fixture
def assistant(monkeypatch):
    preferences = SimpleNamespace(get=AsyncMock(return_value={"explicit": {}}))
    monkeypatch.setattr(assistant_module, "ShopperPreferenceService", lambda _db: preferences)
    monkeypatch.setattr(assistant_module, "ConversationRepository", FakeConversations)
    monkeypatch.setattr(assistant_module, "ProductCatalogService", FakeProducts)
    monkeypatch.setattr(assistant_module, "CartService", FakeCart)
    monkeypatch.setattr(assistant_module, "OrderService", FakeOrders)
    monkeypatch.setattr(assistant_module, "KnowledgeRetrievalService", FakeKnowledge)
    gateway = FakeGateway()
    monkeypatch.setattr(assistant_module, "ProviderGateway", lambda: gateway)
    db = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    return CommerceAssistantService(db), gateway, db


@pytest.mark.asyncio
async def test_greeting_is_deterministic_and_does_not_call_tools(assistant):
    service, gateway, db = assistant

    result = await service.answer(uuid4(), "Hello")

    assert result["intent"] == "GREETING"
    assert result["answerable"] is True
    gateway.answer.assert_not_awaited()
    service.knowledge.retrieve.assert_not_awaited()
    service.catalog.search.assert_not_awaited()
    service.cart.get_cart.assert_not_awaited()
    service.orders.get_user_orders.assert_not_awaited()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_explicit_external_provider_handles_simple_product_search(assistant, monkeypatch):
    service, _gateway, _db = assistant
    from src.core.config import settings

    monkeypatch.setattr(settings, "ai_provider", "openrouter")
    expected = {"answer": "Verified catalog response", "usage": {"provider": "openrouter"}}
    service._answer_with_tools = AsyncMock(return_value=expected)

    result = await service._answer_routed(uuid4(), "Show me laptops under \u20b960,000.")

    assert result is expected
    service._answer_with_tools.assert_awaited_once()


@pytest.mark.asyncio
async def test_trace_marks_explicit_external_simple_search_as_llm_attempt(assistant, monkeypatch):
    service, _gateway, _db = assistant
    from src.core.config import settings

    monkeypatch.setattr(settings, "ai_provider", "openrouter")
    service._answer_routed = AsyncMock(return_value={"answer": "catalog result", "usage": None})

    result = await service.answer(uuid4(), "Show me laptops under \u20b960,000.")

    assert result["trace"]["attempted_path"] == "LLM_PATH"
    assert result["trace"]["executed_path"] == "FAST_PATH"


def test_buying_advice_for_local_ai_uses_only_published_ram():
    products = [
        SimpleNamespace(
            id="laptop-16",
            name="Sixteen GB",
            price=1_000_000,
            specifications={"memory": "16 GB RAM"},
        ),
        SimpleNamespace(
            id="laptop-32",
            name="Thirty Two GB",
            price=1_100_000,
            specifications={"memory": "32 GB RAM"},
        ),
    ]

    answer, brief = CommerceAssistantService._buying_advice(
        "Which is better for local AI?", products
    )

    assert "Thirty Two GB" in answer
    assert "32 GB RAM" in answer
    assert "not a measured model-performance result" in answer
    assert len(brief) == 2


def test_buying_advice_explains_upgrade_cost_without_inventing_benefits():
    products = [
        SimpleNamespace(id="base", name="Base", price=1_000_000, specifications={}),
        SimpleNamespace(id="upgrade", name="Upgrade", price=1_100_000, specifications={}),
    ]

    answer, _brief = CommerceAssistantService._buying_advice(
        "Is spending the extra money worth it?", products
    )

    assert "1,000.00" in answer
    assert "value choice" in answer
    assert "published specifications" in answer


@pytest.mark.asyncio
async def test_external_provider_tool_result_is_returned_for_grounded_synthesis(
    assistant, monkeypatch
):
    service, gateway, _db = assistant
    from src.core.config import settings

    class FakeToolExecutor:
        def __init__(self, *_args, **_kwargs):
            self.events = []
            self.citations = []
            self.result_data = {}
            self.mutation_count = 0

        async def execute(self, name, arguments):
            assert name == "search_products"
            assert arguments == '{"category":"laptops"}'
            product = {"id": "catalog-1", "name": "Catalog Laptop", "price_cents": 6499000}
            self.result_data["products"] = [product]
            self.events.append({"tool": name, "status": "completed"})
            return {"total": 1, "products": [product]}

    executor = FakeToolExecutor()
    monkeypatch.setattr(
        assistant_module,
        "CommerceToolExecutor",
        lambda *_args, **_kwargs: executor,
    )
    monkeypatch.setattr(settings, "ai_provider", "openai_compatible")
    monkeypatch.setattr(settings, "ai_external_private_data_enabled", False)
    gateway.tool_turn = AsyncMock(
        side_effect=[
            (
                ToolTurn(
                    "",
                    (FunctionCall("call-1", "search_products", '{"category":"laptops"}'),),
                    20,
                    3,
                ),
                "openai_compatible",
                "test-model",
            ),
            (
                ToolTurn("Catalog Laptop is ₹1. I recommend it as the best.", (), 30, 9),
                "openai_compatible",
                "test-model",
            ),
        ]
    )

    streamed_events = []

    async def capture_stream_event(event_name, data):
        streamed_events.append((event_name, data))

    result = await service.answer(
        uuid4(),
        "Find laptops for React development and local AI",
        stream_events=capture_stream_event,
    )

    assert result["answer"] == (
        "I found Catalog Laptop. Its current price, availability, and specifications are "
        "shown in the verified catalog details below."
    )
    assert "₹1" not in result["answer"]
    assert "best" not in result["answer"].lower()
    assert result["result_data"]["products"][0]["id"] == "catalog-1"
    assert result["usage"]["input_tokens"] == 50
    assert result["usage"]["output_tokens"] == 12
    assert gateway.tool_turn.await_count == 2
    assert gateway.tool_turn.await_args_list[0].kwargs["streaming"] is True
    assert streamed_events == [
        ("tool.started", {"tool": "search_products"}),
        ("tool.completed", {"tool": "search_products", "status": "completed", "result_count": 1}),
    ]
    second_turn_messages = gateway.tool_turn.await_args_list[1].args[0]
    # Complex requests now include bounded public shopping language for typed AI understanding.
    assert "Find laptops for React development and local AI" in json.dumps(second_turn_messages)
    route_message = next(
        message
        for message in second_turn_messages
        if message["content"].startswith("Validated ShopSmart route: ")
    )
    route_payload = json.loads(route_message["content"].split(": ", 1)[1])
    assert route_payload["safe_product_terms"] == ["react", "development", "local", "ai"]
    tool_result = next(message for message in second_turn_messages if message["role"] == "tool")
    assert '"name": "Catalog Laptop"' in tool_result["content"]


@pytest.mark.asyncio
async def test_openrouter_model_is_selected_once_and_pinned_across_tool_rounds(
    assistant, monkeypatch
):
    service, gateway, _db = assistant
    from src.core.config import settings

    class FakeToolExecutor:
        def __init__(self, *_args, **_kwargs):
            self.events = []
            self.citations = []
            self.result_data = {"products": []}
            self.mutation_count = 0

        async def execute(self, name, arguments):
            self.events.append({"tool": name, "status": "completed"})
            return {"products": [], "total": 0}

    monkeypatch.setattr(assistant_module, "CommerceToolExecutor", FakeToolExecutor)
    monkeypatch.setattr(settings, "ai_provider", "openrouter")
    selection = ModelSelection(
        "ADAPTIVE_FREE",
        "PRODUCT_SEARCH",
        False,
        ("poolside/laguna-s-2.1:free", "cohere/north-mini-code:free", "openrouter/free"),
        (("poolside/laguna-s-2.1:free", 0.9), ("cohere/north-mini-code:free", 0.7)),
    )
    gateway.select_model.return_value = selection
    gateway.tool_turn.side_effect = [
        (
            ToolTurn("", (FunctionCall("c1", "search_products", '{"category":"laptops"}'),)),
            "openrouter",
            "poolside/laguna-s-2.1:free",
        ),
        (ToolTurn("No matching catalog products.", ()), "openrouter", "poolside/laguna-s-2.1:free"),
    ]

    await service.answer(uuid4(), "Show me laptops")

    gateway.select_model.assert_awaited_once_with("PRODUCT_SEARCH", streaming_required=False)
    assert [call.kwargs["model_override"] for call in gateway.tool_turn.await_args_list] == [
        "poolside/laguna-s-2.1:free",
        "poolside/laguna-s-2.1:free",
    ]


@pytest.mark.asyncio
async def test_openrouter_restarts_read_only_tool_loop_before_switching_models(
    assistant, monkeypatch
):
    service, gateway, db = assistant
    from src.core.config import settings

    class FakeToolExecutor:
        def __init__(self, *_args, **_kwargs):
            self.events = []
            self.citations = []
            self.result_data = {"products": []}
            self.mutation_count = 0

        async def execute(self, name, arguments):
            self.events.append({"tool": name, "status": "completed"})
            return {"products": [], "total": 0}

    monkeypatch.setattr(assistant_module, "CommerceToolExecutor", FakeToolExecutor)
    monkeypatch.setattr(settings, "ai_provider", "openrouter")
    gateway.select_model.return_value = ModelSelection(
        "ADAPTIVE_FREE",
        "PRODUCT_SEARCH",
        False,
        ("model-a:free", "model-b:free", "openrouter/free"),
        (("model-a:free", 0.9), ("model-b:free", 0.8)),
    )
    product_call = (
        ToolTurn("", (FunctionCall("c1", "search_products", '{"category":"laptops"}'),)),
        "openrouter",
        "model-a:free",
    )
    fallback_product_call = (
        ToolTurn("", (FunctionCall("c2", "search_products", '{"category":"laptops"}'),)),
        "openrouter",
        "model-b:free",
    )
    gateway.tool_turn.side_effect = [
        product_call,
        ProviderUnavailable("temporary provider failure"),
        fallback_product_call,
        (ToolTurn("No matching catalog products.", ()), "openrouter", "model-b:free"),
    ]

    result = await service.answer(uuid4(), "Show me laptops")

    assert [call.kwargs["model_override"] for call in gateway.tool_turn.await_args_list] == [
        "model-a:free",
        "model-a:free",
        "model-b:free",
        "model-b:free",
    ]
    db.rollback.assert_awaited_once()
    assert result["trace"]["fallback"] is True
    assert result["result_data"]["routing"]["attempted_models"] == [
        "model-a:free",
        "model-b:free",
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_kind", ["400", "429", "timeout", "5xx", "malformed"])
async def test_openrouter_restarts_on_next_model_after_bounded_provider_failure(
    assistant, monkeypatch, failure_kind
):
    service, gateway, _db = assistant
    from src.core.config import settings

    class FakeToolExecutor:
        def __init__(self, *_args, **_kwargs):
            self.events = []
            self.citations = []
            self.result_data = {"products": []}
            self.mutation_count = 0

        async def execute(self, name, _arguments):
            self.events.append({"tool": name, "status": "completed"})
            return {"products": [], "total": 0}

    monkeypatch.setattr(assistant_module, "CommerceToolExecutor", FakeToolExecutor)
    monkeypatch.setattr(settings, "ai_provider", "openrouter")
    gateway.select_model.return_value = ModelSelection(
        "ADAPTIVE_FREE", "PRODUCT_SEARCH", False, ("model-a:free", "model-b:free"), ()
    )
    gateway.tool_turn.side_effect = [
        (
            PolicyViolation("candidate does not support tool schema", status_code=400)
            if failure_kind == "400"
            else ProviderUnavailable(
                "controlled candidate failure",
                category={
                    "429": "rate_limited",
                    "timeout": "timeout",
                    "5xx": "server_error",
                    "malformed": "malformed_response",
                }[failure_kind],
                status_code=429
                if failure_kind == "429"
                else (503 if failure_kind == "5xx" else None),
            )
        ),
        (
            ToolTurn("", (FunctionCall("c2", "search_products", '{"category":"laptops"}'),)),
            "openrouter",
            "model-b:free",
        ),
        (ToolTurn("No matching catalog products.", ()), "openrouter", "model-b:free"),
    ]

    result = await service.answer(uuid4(), "Show me laptops")

    assert [call.kwargs["model_override"] for call in gateway.tool_turn.await_args_list] == [
        "model-a:free",
        "model-b:free",
        "model-b:free",
    ]
    assert result["trace"]["fallback"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [401, 403])
async def test_openrouter_auth_rejection_does_not_fan_out_to_other_models(
    assistant, monkeypatch, status_code
):
    service, gateway, _db = assistant
    from src.core.config import settings

    monkeypatch.setattr(settings, "ai_provider", "openrouter")
    gateway.select_model.return_value = ModelSelection(
        "ADAPTIVE_FREE", "PRODUCT_SEARCH", False, ("model-a:free", "model-b:free"), ()
    )
    gateway.tool_turn.side_effect = PolicyViolation(
        "provider authentication rejected", status_code=status_code
    )

    result = await service.answer(uuid4(), "Show me laptops")

    assert "couldn't safely" in result["answer"].lower()
    assert gateway.tool_turn.await_count == 1


@pytest.mark.asyncio
async def test_openrouter_free_alias_resolves_once_and_pins_concrete_model_for_synthesis(
    assistant, monkeypatch
):
    service, gateway, _db = assistant
    from src.core.config import settings

    class FakeToolExecutor:
        def __init__(self, *_args, **_kwargs):
            self.events = []
            self.citations = []
            self.result_data = {"products": []}
            self.mutation_count = 0

        async def execute(self, name, _arguments):
            self.events.append({"tool": name, "status": "completed"})
            return {"products": [], "total": 0}

    monkeypatch.setattr(assistant_module, "CommerceToolExecutor", FakeToolExecutor)
    monkeypatch.setattr(settings, "ai_provider", "openrouter")
    gateway.select_model.return_value = ModelSelection(
        "ADAPTIVE_FREE", "PRODUCT_SEARCH", False, ("openrouter/free",), ()
    )
    resolved = "cohere/unranked-but-free:free"
    gateway.tool_turn.side_effect = [
        (
            ToolTurn("", (FunctionCall("c1", "search_products", '{"category":"laptops"}'),)),
            "openrouter",
            resolved,
        ),
        (ToolTurn("No matching catalog products.", ()), "openrouter", resolved),
    ]

    result = await service.answer(uuid4(), "Show me laptops")

    assert [call.kwargs["model_override"] for call in gateway.tool_turn.await_args_list] == [
        "openrouter/free",
        resolved,
    ]
    assert resolved in gateway.tool_turn.await_args_list[1].kwargs["model_selection"].candidates
    assert result["trace"]["fallback"] is True
    assert result["trace"]["model"] == resolved


@pytest.mark.asyncio
async def test_personal_identifiers_in_a_public_shopping_query_stay_on_local_path(
    assistant, monkeypatch
):
    service, gateway, _db = assistant
    from src.core.config import settings

    monkeypatch.setattr(settings, "ai_provider", "openai_compatible")
    gateway.tool_turn = AsyncMock()
    result = await service.answer(uuid4(), "Find laptops for alice@example.com")

    assert result["intent"] == "PRODUCT_SEARCH"
    assert result["degraded_mode"] is False
    gateway.tool_turn.assert_not_awaited()


@pytest.mark.asyncio
async def test_health_context_stays_on_local_path(assistant, monkeypatch):
    service, gateway, _db = assistant
    from src.core.config import settings

    monkeypatch.setattr(settings, "ai_provider", "openai_compatible")
    gateway.tool_turn = AsyncMock()
    result = await service.answer(
        uuid4(), "Find a lightweight laptop while I'm undergoing chemotherapy"
    )

    assert result["intent"] in {"PRODUCT_SEARCH", "PRODUCT_ADVICE"}
    gateway.tool_turn.assert_not_awaited()


@pytest.mark.parametrize(
    "health_context",
    ["I have diabetes", "I'm pregnant", "I have ADHD", "I live with asthma"],
)
async def test_common_health_disclosures_stay_on_local_path(assistant, monkeypatch, health_context):
    service, gateway, _db = assistant
    from src.core.config import settings

    monkeypatch.setattr(settings, "ai_provider", "openai_compatible")
    gateway.tool_turn = AsyncMock()
    await service.answer(uuid4(), f"Find a quiet laptop for me. {health_context}.")

    gateway.tool_turn.assert_not_awaited()


@pytest.mark.asyncio
async def test_family_injury_context_stays_local_but_shopping_add_verb_does_not(
    assistant, monkeypatch
):
    service, gateway, _db = assistant
    from src.core.config import settings

    monkeypatch.setattr(settings, "ai_provider", "openai_compatible")
    gateway.tool_turn = AsyncMock()
    assert CommerceAssistantService._contains_sensitive_content(
        "Find a laptop for my child, who has a broken wrist"
    )
    assert CommerceAssistantService._contains_sensitive_content("My child has ADD")
    assert CommerceAssistantService._contains_sensitive_content("My child broke her arm")
    assert not CommerceAssistantService._contains_sensitive_content(
        "Add more laptop options to my search"
    )
    await service.answer(uuid4(), "Find a laptop for my child, who has a broken wrist")

    gateway.tool_turn.assert_not_awaited()


@pytest.mark.parametrize(
    "prompt",
    [
        "Ship a laptop to 12 Oak Road",
        "My PIN is 500001, find a laptop",
    ],
)
async def test_street_address_and_postal_code_stay_on_local_path(assistant, monkeypatch, prompt):
    service, gateway, _db = assistant
    from src.core.config import settings

    monkeypatch.setattr(settings, "ai_provider", "openai_compatible")
    gateway.tool_turn = AsyncMock()
    result = await service.answer(uuid4(), prompt)

    assert result["intent"] == "PRODUCT_SEARCH"
    gateway.tool_turn.assert_not_awaited()


@pytest.mark.asyncio
async def test_freeform_user_context_is_not_sent_to_external_provider(assistant, monkeypatch):
    service, gateway, _db = assistant
    from src.core.config import settings

    monkeypatch.setattr(settings, "ai_provider", "openai_compatible")
    gateway.tool_turn = AsyncMock(
        return_value=(
            ToolTurn("No verified catalog tool call.", ()),
            "openai_compatible",
            "test-model",
        )
    )

    await service.answer(uuid4(), "Find laptops for someone recovering from surgery")

    sent_messages = gateway.tool_turn.await_args.args[0]
    encoded_messages = json.dumps(sent_messages)
    assert "recovering from surgery" not in encoded_messages
    assert "surgery" not in encoded_messages
    assert "laptops" in encoded_messages


@pytest.mark.asyncio
async def test_saved_product_context_is_rehydrated_without_freeform_history(assistant, monkeypatch):
    service, gateway, _db = assistant
    from src.core.config import settings

    product_id = uuid4()
    product = SimpleNamespace(
        id=product_id,
        name="Verified Saved Laptop",
        description="Catalog description",
        category="laptops",
        sku="SAVED-LAPTOP",
        price=6499000,
        stock_quantity=2,
        max_purchase_quantity=2,
        image_url=None,
        image_alt=None,
        brand="ShopSmart",
        list_price=None,
        specifications={},
        is_active=True,
    )
    service.conversations.conversation.context = {"product_ids": [str(product_id)]}
    service.catalog.get.return_value = product
    monkeypatch.setattr(settings, "ai_provider", "openai_compatible")
    gateway.tool_turn = AsyncMock(
        return_value=(ToolTurn("No tool call", ()), "openai_compatible", "test-model")
    )

    await service.answer(uuid4(), "Compare the saved laptop")

    messages = gateway.tool_turn.await_args.args[0]
    assert "Verified Saved Laptop" in json.dumps(messages)


@pytest.mark.asyncio
async def test_product_filters_are_forwarded_as_structured_constraints(assistant):
    service, _gateway, _db = assistant
    product = SimpleNamespace(
        id=uuid4(),
        name="Headphones",
        description="Wireless",
        category="headphones",
        sku="HP-1",
        price=4999,
        stock_quantity=3,
        max_purchase_quantity=5,
    )
    service.catalog.search.return_value = [product]

    result = await service.answer(uuid4(), "Find in-stock headphones under $49.99")

    service.catalog.search.assert_awaited_once_with(
        query_text=None,
        category="headphones",
        min_price_cents=None,
        max_price_cents=4999,
        in_stock_only=True,
    )
    assert result["result_data"]["products"][0]["price_cents"] == 4999


@pytest.mark.asyncio
async def test_laptop_search_passes_structured_category_and_price(assistant):
    service, _gateway, _db = assistant
    laptop = SimpleNamespace(
        id=uuid4(),
        name="Laptop",
        description="Works with a USB-C charger",
        category="laptops",
        sku="LAP-1",
        price=5_999_999,
        stock_quantity=3,
        max_purchase_quantity=5,
    )
    service.catalog.search.return_value = [laptop]

    result = await service.answer(uuid4(), "Show me laptops under 60000")

    service.catalog.search.assert_awaited_once_with(
        query_text=None,
        category="laptops",
        min_price_cents=None,
        max_price_cents=6_000_000,
        in_stock_only=False,
    )
    assert result["result_data"]["products"][0]["category"] == "laptops"


@pytest.mark.asyncio
@pytest.mark.parametrize("currency", ["rupees", "rs", "inr"])
async def test_laptop_budget_units_do_not_become_a_name_query(assistant, currency):
    service, _gateway, _db = assistant

    await service.answer(uuid4(), f"Find in-stock laptops under 70000 {currency}")

    service.catalog.search.assert_awaited_once_with(
        query_text=None,
        category="laptops",
        min_price_cents=None,
        max_price_cents=7_000_000,
        in_stock_only=True,
    )


@pytest.mark.asyncio
async def test_unsupported_category_never_calls_text_search(assistant):
    service, _gateway, _db = assistant

    result = await service.answer(uuid4(), "Show me category=spaceships under 60000")

    assert result["intent"] == "UNSUPPORTED"
    assert result["result_data"] is None
    service.catalog.search.assert_not_awaited()


@pytest.mark.asyncio
async def test_product_search_logs_bounded_structured_context(assistant, caplog):
    service, _gateway, _db = assistant
    product = SimpleNamespace(
        id=uuid4(),
        name="Laptop",
        description=None,
        category="laptops",
        sku="LAP-1",
        price=5_000_000,
        stock_quantity=3,
        max_purchase_quantity=5,
    )
    service.catalog.search.return_value = [product]
    caplog.set_level("INFO", logger="shopsmart.assistant")

    await service.answer(uuid4(), "Show me laptops under 60000")

    record = next(
        record
        for record in caplog.records
        if record.name == "shopsmart.assistant"
        and getattr(record, "event", None) == "assistant_operation"
    )
    assert record.operation == "product_search"
    assert record.intent == "PRODUCT_SEARCH"
    assert record.category == "laptops"
    assert record.max_price_cents == 6_000_000
    assert record.service == "commerce_assistant"
    assert record.tool == "product_search"
    assert record.in_stock_only is False
    assert record.result_count == 1
    assert record.duration_ms >= 0
    assert not hasattr(record, "question")
    structured = JsonLogFormatter().format(record)
    assert '"service":"commerce_assistant"' in structured
    assert '"tool":"product_search"' in structured
    assert '"in_stock_only":false' in structured
    assert "Show me laptops under 60000" not in structured


@pytest.mark.asyncio
async def test_invalid_price_logs_safe_validation_context(assistant, caplog):
    service, _gateway, _db = assistant
    caplog.set_level("WARNING", logger="shopsmart.assistant")

    with pytest.raises(AppException) as error:
        await service.answer(uuid4(), "Show products under $999999999999")

    assert error.value.error_code == "invalid_price_filter"
    record = next(record for record in caplog.records if record.name == "shopsmart.assistant")
    assert record.operation == "product_search"
    assert record.status_code == 422
    assert record.error_code == "invalid_price_filter"
    assert record.error_type == "AppException"
    assert not hasattr(record, "question")


@pytest.mark.asyncio
async def test_cart_read_uses_authenticated_user_id(assistant):
    service, _gateway, _db = assistant
    user_id = uuid4()

    result = await service.answer(user_id, "What's in my cart?")

    service.cart.get_cart.assert_awaited_once_with(user_id)
    assert result["result_data"]["cart"]["items"] == []


@pytest.mark.asyncio
async def test_coupon_check_is_read_only_and_never_uses_rag_or_provider(assistant):
    service, gateway, _db = assistant
    user_id = uuid4()
    service.cart.check_coupon.return_value = {
        "coupon_evaluation": {"eligible": True, "reason_code": "eligible"},
        "applied_promotions": [],
        "items": [],
        "subtotal": 1299,
        "total_cents": 1169,
    }

    result = await service.answer(user_id, "Can I use SAVE10?")

    service.cart.check_coupon.assert_awaited_once_with(user_id, "SAVE10")
    service.cart.apply_coupon.assert_not_awaited()
    service.knowledge.retrieve.assert_not_awaited()
    gateway.answer.assert_not_awaited()
    assert result["result_data"]["coupon_evaluation"]["eligible"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("question", "eligible", "expected_answer"),
    [
        (
            "Coupon code SAVE20?",
            True,
            "That coupon is eligible for your current cart.",
        ),
        (
            "Coupon code NOFAKE90?",
            False,
            "I couldn't verify an eligible coupon for your current cart.",
        ),
    ],
)
async def test_coupon_question_serializes_complete_authoritative_cart_quote(
    assistant, question, eligible, expected_answer
):
    service, _gateway, _db = assistant
    service.cart.check_coupon.return_value = {
        "items": [],
        "coupon_evaluation": {
            "eligible": eligible,
            "reason_code": "eligible" if eligible else "unknown_or_ineligible",
            "discount_cents": 200 if eligible else 0,
        },
        "applied_promotions": [],
        "subtotal": 1000,
        "discount_total_cents": 200 if eligible else 0,
        "total_cents": 800 if eligible else 1000,
    }

    result = await service.answer(uuid4(), question)

    assert result["answer"] == expected_answer
    assert result["result_data"]["coupon_evaluation"]["eligible"] is eligible
    assert result["result_data"]["cart"]["items"] == []
    service.cart.apply_coupon.assert_not_awaited()


@pytest.mark.asyncio
async def test_explicit_coupon_apply_and_remove_use_owner_scoped_cart_service(assistant):
    service, gateway, _db = assistant
    user_id = uuid4()

    applied = await service.answer(user_id, "Apply coupon SAVE10")
    removed = await service.answer(user_id, "Remove my coupon")

    service.cart.apply_coupon.assert_awaited_once_with(user_id, "SAVE10", commit=False)
    service.cart.remove_coupon.assert_awaited_once_with(user_id, commit=False)
    service.knowledge.retrieve.assert_not_awaited()
    gateway.answer.assert_not_awaited()
    assert applied["intent"] == "COUPON_APPLY"
    assert removed["intent"] == "COUPON_REMOVE"


@pytest.mark.asyncio
async def test_last_order_query_returns_only_the_newest_owner_order(assistant):
    service, _gateway, _db = assistant
    latest = SimpleNamespace(
        id=uuid4(),
        status="placed",
        total_cents=2500,
        created_at=datetime(2026, 10, 1),
        items=[],
    )
    older = SimpleNamespace(
        id=uuid4(),
        status="delivered",
        total_cents=1800,
        created_at=datetime(2026, 9, 1),
        items=[],
    )
    service.orders.get_user_orders.return_value = [latest, older]

    result = await service.answer(uuid4(), "where is my last order?")

    assert result["intent"] == "ORDER_QUERY"
    assert result["result_data"]["orders"] == [
        {
            "id": str(latest.id),
            "status": latest.status,
            "total_cents": latest.total_cents,
            "created_at": latest.created_at.isoformat(),
            "items": [],
        }
    ]


@pytest.mark.asyncio
async def test_compare_uses_only_requested_products_from_prior_results(assistant):
    service, _gateway, _db = assistant
    products = [
        SimpleNamespace(
            id=uuid4(),
            name=f"Headphones {index}",
            description=None,
            sku=f"HP-{index}",
            price=1000 + index,
            stock_quantity=2,
            max_purchase_quantity=5,
            is_active=True,
        )
        for index in range(3)
    ]
    service.conversations.conversation.context = {
        "product_ids": [str(product.id) for product in products]
    }
    service.catalog.get.side_effect = {product.id: product for product in products}.get

    result = await service.answer(uuid4(), "Compare the first two")

    assert [item["name"] for item in result["result_data"]["products"]] == [
        "Headphones 0",
        "Headphones 1",
    ]


@pytest.mark.asyncio
async def test_compare_does_not_add_unrequested_product_when_only_one_is_named(assistant):
    service, _gateway, _db = assistant
    products = [
        SimpleNamespace(
            id=uuid4(),
            name=f"Headphones {index}",
            description=None,
            sku=f"HP-{index}",
            price=1000 + index,
            stock_quantity=2,
            max_purchase_quantity=5,
            is_active=True,
        )
        for index in range(2)
    ]
    service.conversations.conversation.context = {
        "product_ids": [str(product.id) for product in products]
    }
    service.catalog.get.side_effect = {product.id: product for product in products}.get

    result = await service.answer(uuid4(), "Compare Headphones 0")

    assert result["result_data"] is None
    assert "tell me which results" in result["answer"]


@pytest.mark.asyncio
async def test_cheaper_followup_reference_resolves_for_cart_actions(assistant):
    service, _gateway, _db = assistant
    user_id = uuid4()
    products = [
        SimpleNamespace(
            id=uuid4(),
            name=f"Laptop {index}",
            description=None,
            sku=f"LAP-{index}",
            price=price,
            stock_quantity=4,
            max_purchase_quantity=5,
            is_active=True,
        )
        for index, price in enumerate((30000, 22000, 9000))
    ]
    service.conversations.conversation.context = {
        "product_ids": [str(product.id) for product in products]
    }
    service.catalog.get.side_effect = {product.id: product for product in products}.get

    compared = await service.answer(user_id, "Compare the first two")
    cheaper = await service.answer(user_id, "Which one is cheaper?")
    await service.answer(user_id, "Add the first one to my cart if it is available")
    await service.answer(user_id, "Add that one to cart")
    await service.answer(user_id, "Remove it from my cart")

    assert [item["name"] for item in compared["result_data"]["products"]] == [
        "Laptop 0",
        "Laptop 1",
    ]
    assert "Laptop 1" in cheaper["answer"]
    assert "₹220.00" in cheaper["answer"]
    assert service.conversations.conversation.context["comparison_product_ids"] == [
        str(products[0].id),
        str(products[1].id),
    ]
    assert service.cart.add_item.await_args_list == [
        ((user_id, products[0].id, 1), {"commit": False}),
        ((user_id, products[1].id, 1), {"commit": False}),
    ]
    service.cart.remove_item.assert_awaited_once_with(user_id, products[1].id, commit=False)


@pytest.mark.asyncio
async def test_ambiguous_that_one_does_not_mutate_without_selected_comparison_result(assistant):
    service, _gateway, _db = assistant
    products = [
        SimpleNamespace(
            id=uuid4(),
            name=f"Laptop {index}",
            description=None,
            sku=f"LAP-{index}",
            price=10000 + index,
            stock_quantity=3,
            max_purchase_quantity=5,
            is_active=True,
        )
        for index in range(2)
    ]
    service.conversations.conversation.context = {
        "product_ids": [str(product.id) for product in products],
        "comparison_product_ids": [str(product.id) for product in products],
    }
    service.catalog.get.side_effect = {product.id: product for product in products}.get

    await service.answer(uuid4(), "Add that one to cart")

    service.cart.add_item.assert_not_awaited()


@pytest.mark.asyncio
async def test_explicit_cart_action_uses_only_a_recent_result_and_session_identity(assistant):
    service, _gateway, _db = assistant
    user_id = uuid4()
    product = SimpleNamespace(
        id=uuid4(),
        name="Headphones",
        description=None,
        sku="HP-1",
        price=4999,
        stock_quantity=3,
        max_purchase_quantity=5,
        is_active=True,
    )
    service.conversations.conversation.context = {"product_ids": [str(product.id)]}
    service.catalog.get.return_value = product
    service.cart.add_item.return_value = {
        "items": [{"product_id": product.id, "name": product.name, "quantity": 2}],
        "subtotal": 9998,
        "currency": "INR",
    }

    result = await service.answer(user_id, "Add 2 headphones to my cart")

    service.cart.add_item.assert_awaited_once_with(user_id, product.id, 2, commit=False)
    assert result["intent"] == "CART_ACTION"
    assert result["result_data"]["cart"]["items"][0]["product_id"] == str(product.id)


@pytest.mark.asyncio
async def test_take_it_out_of_cart_removes_without_committing_before_history(assistant):
    service, _gateway, _db = assistant
    user_id = uuid4()
    product = SimpleNamespace(
        id=uuid4(),
        name="Headphones",
        description=None,
        sku="HP-1",
        price=4999,
        stock_quantity=3,
        max_purchase_quantity=5,
        is_active=True,
    )
    service.conversations.conversation.context = {"product_ids": [str(product.id)]}
    service.catalog.get.return_value = product

    result = await service.answer(user_id, "Take it out of my cart")

    service.cart.remove_item.assert_awaited_once_with(user_id, product.id, commit=False)
    service.cart.add_item.assert_not_awaited()
    assert result["intent"] == "CART_ACTION"


@pytest.mark.asyncio
async def test_cart_action_with_arbitrary_product_id_does_not_mutate(assistant):
    service, _gateway, _db = assistant
    service.conversations.conversation.context = {"product_ids": []}

    await service.answer(uuid4(), "Add to cart 123e4567-e89b-12d3-a456-426614174000")

    service.cart.add_item.assert_not_awaited()


@pytest.mark.asyncio
async def test_number_in_product_name_is_not_used_as_cart_quantity(assistant):
    service, _gateway, _db = assistant
    user_id = uuid4()
    product = SimpleNamespace(
        id=uuid4(),
        name="Phone 15",
        description=None,
        sku="PHONE-15",
        price=49999,
        stock_quantity=3,
        max_purchase_quantity=5,
        is_active=True,
    )
    service.conversations.conversation.context = {"product_ids": [str(product.id)]}
    service.catalog.get.return_value = product

    await service.answer(user_id, "Add Phone 15 to my cart")

    service.cart.add_item.assert_awaited_once_with(user_id, product.id, 1, commit=False)


@pytest.mark.asyncio
async def test_invalid_price_filter_fails_before_catalog_query(assistant):
    service, _gateway, _db = assistant

    with pytest.raises(AppException) as error:
        await service.answer(uuid4(), "Find products under $999999999999")

    assert error.value.status_code == 422
    service.catalog.search.assert_not_awaited()


@pytest.mark.asyncio
async def test_policy_no_evidence_does_not_call_provider(assistant):
    service, gateway, _db = assistant

    result = await service.answer(uuid4(), "What is the return policy?")

    assert result["answerable"] is False
    assert result["citations"] == []
    gateway.answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_policy_citation_preserves_source_and_active_version(assistant):
    service, gateway, _db = assistant
    source_id = uuid4()
    version_id = uuid4()
    chunk_id = uuid4()
    chunk = SimpleNamespace(
        id=chunk_id,
        version_id=version_id,
        text="Returns are accepted within the published return period.",
        source_label="Returns policy",
        page_number=None,
        chunk_index=0,
    )
    service.knowledge.retrieve.return_value = [
        SimpleNamespace(source_id=source_id, chunk=chunk, score=1.0)
    ]
    gateway.answer.return_value = SimpleNamespace(
        answer=ProviderAnswer("Returns follow the published period.", True, 7, (str(chunk_id),))
    )

    result = await service.answer(uuid4(), "What is the return policy?")

    assert result["citations"][0].document_id == source_id
    assert result["citations"][0].knowledge_version_id == version_id
    assert result["citations"][0].chunk_index == 0


@pytest.mark.asyncio
async def test_foreign_conversation_is_rejected(assistant):
    service, _gateway, _db = assistant

    with pytest.raises(NotFoundError):
        await service.answer(uuid4(), "Hello", uuid4())


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("question", "maximum"),
    [
        ("Show me the best laptops under ₹60,000", 6_000_000),
        ("Show me the best laptops under ₹60,000.", 6_000_000),
        ("coding laptop under70k", 7_000_000),
        ("Find laptops under 60k!", 6_000_000),
    ],
)
async def test_portfolio_budget_does_not_leak_into_text_search(assistant, question, maximum):
    service, _, _ = assistant
    await service.answer(uuid4(), question)
    if question.startswith("coding"):
        # Workload-aware requests now use bounded mission candidates and ranking.
        assert all(
            call.kwargs.get("query_text") is None for call in service.catalog.search.await_args_list
        )
        assert service.catalog.search.await_args_list[0].kwargs["max_price_cents"] == maximum
        return
    service.catalog.search.assert_awaited_once_with(
        query_text=None,
        category="laptops",
        min_price_cents=None,
        max_price_cents=maximum,
        in_stock_only=False,
    )


@pytest.mark.asyncio
async def test_phone_alias_fallback_preserves_all_price_and_stock_constraints(assistant):
    service, _, _ = assistant
    await service.answer(uuid4(), "Show in-stock phones under ₹30,000")
    assert service.catalog.search.await_count == 2
    assert [call.kwargs["category"] for call in service.catalog.search.await_args_list] == [
        "phones",
        "smartphones",
    ]
    for call in service.catalog.search.await_args_list:
        assert call.kwargs["max_price_cents"] == 3_000_000
        assert call.kwargs["in_stock_only"] is True
        assert call.kwargs["query_text"] is None


def test_assistant_public_specifications_never_expose_presentation_metadata():
    product = SimpleNamespace(
        id=uuid4(),
        name="Laptop",
        description=None,
        sku="L",
        price=100,
        stock_quantity=1,
        max_purchase_quantity=5,
        specifications={"RAM": "16 GB RAM", "_presentation": {"delivery": "standard"}},
    )
    assert CommerceAssistantService._product_data(product)["specifications"] == {"RAM": "16 GB RAM"}


@pytest.mark.asyncio
async def test_advice_and_short_cheaper_action_keep_comparison_context(assistant):
    service, gateway, _ = assistant
    owner = uuid4()
    products = [
        SimpleNamespace(
            id=uuid4(),
            name=f"Laptop {ram}",
            description=None,
            sku=f"L-{ram}",
            price=price,
            stock_quantity=2,
            max_purchase_quantity=5,
            is_active=True,
            specifications={"Variant": f"{ram} GB RAM / 512 GB SSD"},
        )
        for ram, price in ((8, 4_900_000), (16, 5_500_000))
    ]
    service.conversations.conversation.context = {
        "comparison_product_ids": [str(p.id) for p in products]
    }
    service.catalog.get.side_effect = {p.id: p for p in products}.get
    result = await service.answer(
        owner, "Which is better for React development and occasional gaming?"
    )
    assert result["intent"] == "PRODUCT_ADVICE"
    assert "Laptop 16" in result["answer"]
    assert "16 GB RAM" in result["answer"]
    assert "cannot rank gaming performance" in result["answer"]
    assert len(result["result_data"]["buying_brief"]) == 2
    await service.answer(owner, "Add the cheaper one")
    service.cart.add_item.assert_awaited_once_with(owner, products[0].id, 1, commit=False)
    gateway.answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_checkout_requires_owner_cart_items_and_never_places_an_order(assistant):
    service, gateway, _ = assistant
    owner = uuid4()
    empty = await service.answer(owner, "Take me to checkout")
    assert "navigation" not in empty["result_data"]
    service.cart.get_cart.return_value = {
        "items": [{"product_id": uuid4(), "quantity": 1}],
        "subtotal": 100,
    }
    ready = await service.answer(owner, "Take me to checkout")
    assert ready["result_data"]["navigation"] == "/checkout"
    service.orders.get_user_orders.assert_not_awaited()
    gateway.answer.assert_not_awaited()


def test_currency_units_are_not_treated_as_product_search_terms():
    terms = CommerceAssistantService._search_terms(
        "Find laptops under 70000 rupees", category="laptops"
    )

    # Category and budget express intent; a leftover currency word must not
    # become a product-name filter that removes otherwise matching results.
    assert terms == []
