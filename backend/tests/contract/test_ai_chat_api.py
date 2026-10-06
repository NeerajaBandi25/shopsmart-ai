import json
from uuid import UUID, uuid4

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import hash_password
from src.models.product import Product
from src.repositories.user_repository import UserRepository
from src.services.assistant_knowledge import KnowledgeIngestionService
from src.services.cart_service import CartService
from src.services.order_service import OrderService


async def test_replayed_assistant_cart_mutation_returns_original_result_once(
    test_client: AsyncClient,
    test_db: AsyncSession,
    test_user_data_in_db: dict,
):
    product = Product(
        name="Idempotency Contract Laptop",
        description="A local cart replay fixture",
        category="laptops",
        brand="Vellune",
        sku=f"IDEMPOTENCY-{uuid4().hex[:12]}",
        price=5_000_000,
        stock_quantity=3,
        max_purchase_quantity=2,
        is_active=True,
        specifications={"ram": "16 GB"},
    )
    test_db.add(product)
    await test_db.commit()
    login = await test_client.post("/api/v1/auth/login", json=test_user_data_in_db)
    csrf = await test_client.get("/api/v1/auth/csrf", cookies=login.cookies)
    headers = {"X-CSRF-Token": csrf.json()["csrf_token"]}

    search = await test_client.post(
        "/api/v1/ai/chat",
        cookies=login.cookies,
        headers=headers,
        json={"question": "Show me laptops under ₹60,000."},
    )
    assert search.status_code == 200
    conversation_id = search.json()["conversation_id"]
    request_id = str(uuid4())
    mutation = {
        "request_id": request_id,
        "conversation_id": conversation_id,
        "question": "Add the recommended one.",
    }
    first = await test_client.post(
        "/api/v1/ai/chat", cookies=login.cookies, headers=headers, json=mutation
    )
    replay = await test_client.post(
        "/api/v1/ai/chat", cookies=login.cookies, headers=headers, json=mutation
    )

    assert first.status_code == replay.status_code == 200
    assert first.json()["message_id"] == replay.json()["message_id"]
    cart = await test_client.get("/api/v1/cart", cookies=login.cookies)
    assert cart.status_code == 200
    assert [(item["product_id"], item["quantity"]) for item in cart.json()["items"]] == [
        (str(product.id), 1)
    ]
    removed = await test_client.delete(
        f"/api/v1/cart/items/{product.id}", cookies=login.cookies, headers=headers
    )
    assert removed.status_code == 200
    await test_client.delete(
        f"/api/v1/ai/conversations/{conversation_id}", cookies=login.cookies, headers=headers
    )


async def test_idempotency_keys_are_owner_scoped_and_conversation_payload_is_exact(
    test_client: AsyncClient,
    test_db: AsyncSession,
    test_user_data_in_db: dict,
):
    first_login = await test_client.post("/api/v1/auth/login", json=test_user_data_in_db)
    first_csrf = await test_client.get("/api/v1/auth/csrf", cookies=first_login.cookies)
    first_headers = {"X-CSRF-Token": first_csrf.json()["csrf_token"]}
    request_id = str(uuid4())
    first = await test_client.post(
        "/api/v1/ai/chat",
        cookies=first_login.cookies,
        headers=first_headers,
        json={"question": "Hello", "request_id": request_id},
    )
    assert first.status_code == 200

    second_password = "AnotherSecurePassword123!"
    await UserRepository(test_db).create_user(
        "idempotency-other-owner@example.test", hash_password(second_password)
    )
    await test_db.commit()
    second_login = await test_client.post(
        "/api/v1/auth/login",
        json={"email": "idempotency-other-owner@example.test", "password": second_password},
    )
    second_csrf = await test_client.get("/api/v1/auth/csrf", cookies=second_login.cookies)
    second = await test_client.post(
        "/api/v1/ai/chat",
        cookies=second_login.cookies,
        headers={"X-CSRF-Token": second_csrf.json()["csrf_token"]},
        json={"question": "Hello", "request_id": request_id},
    )
    assert second.status_code == 200

    reused_with_conversation = await test_client.post(
        "/api/v1/ai/chat",
        cookies=first_login.cookies,
        headers=first_headers,
        json={
            "question": "Hello",
            "request_id": request_id,
            "conversation_id": first.json()["conversation_id"],
        },
    )
    assert reused_with_conversation.status_code == 409

    explicit_request_id = str(uuid4())
    explicit = await test_client.post(
        "/api/v1/ai/chat",
        cookies=first_login.cookies,
        headers=first_headers,
        json={
            "question": "Hello",
            "request_id": explicit_request_id,
            "conversation_id": first.json()["conversation_id"],
        },
    )
    assert explicit.status_code == 200
    omitted_conversation = await test_client.post(
        "/api/v1/ai/chat",
        cookies=first_login.cookies,
        headers=first_headers,
        json={"question": "Hello", "request_id": explicit_request_id},
    )
    assert omitted_conversation.status_code == 409


async def test_assistant_chat_requires_auth_and_csrf_and_returns_commerce_contract(
    test_client: AsyncClient, test_user_data_in_db: dict
):
    anonymous = await test_client.post("/api/v1/ai/chat", json={"question": "Hello"})
    assert anonymous.status_code == 401

    login = await test_client.post("/api/v1/auth/login", json=test_user_data_in_db)
    assert login.status_code == 200
    csrf = await test_client.get("/api/v1/auth/csrf", cookies=login.cookies)
    assert csrf.status_code == 200

    missing_csrf = await test_client.post(
        "/api/v1/ai/chat", cookies=login.cookies, json={"question": "Hello"}
    )
    assert missing_csrf.status_code == 403

    response = await test_client.post(
        "/api/v1/ai/chat",
        cookies=login.cookies,
        headers={"X-CSRF-Token": csrf.json()["csrf_token"]},
        json={"question": "Hello"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "GREETING"
    assert payload["answer"].startswith("Hi!")
    assert payload["citations"] == []
    assert "provider" not in payload
    assert "model" not in payload
    assert "retrieval_count" not in payload
    assert "token_count" not in payload
    assert "estimated_cost_usd" not in payload


async def test_assistant_sse_stream_requires_auth_and_returns_verified_completion(
    test_client: AsyncClient, test_user_data_in_db: dict
):
    anonymous = await test_client.post("/api/v1/ai/chat/stream", json={"question": "Hello"})
    assert anonymous.status_code == 401

    login = await test_client.post("/api/v1/auth/login", json=test_user_data_in_db)
    csrf = await test_client.get("/api/v1/auth/csrf", cookies=login.cookies)
    response = await test_client.post(
        "/api/v1/ai/chat/stream",
        cookies=login.cookies,
        headers={"X-CSRF-Token": csrf.json()["csrf_token"]},
        json={"question": "Hello"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = []
    for frame in response.text.strip().split("\n\n"):
        lines = frame.splitlines()
        event_name = next(line[6:].strip() for line in lines if line.startswith("event:"))
        data = json.loads(next(line[5:] for line in lines if line.startswith("data:")))
        events.append((event_name, data))
    assert events[0][0] == "assistant.started"
    assert any(name == "assistant.delta" for name, _ in events)
    completed = next(data for name, data in events if name == "assistant.completed")
    assert completed["intent"] == "GREETING"
    assert completed["answer"].startswith("Hi!")


async def test_assistant_sse_stream_sanitizes_internal_errors(
    monkeypatch, test_client: AsyncClient, test_user_data_in_db: dict
):
    async def fail_with_secret(*_args, **_kwargs):
        raise RuntimeError("provider response contained private diagnostic data")

    monkeypatch.setattr("src.api.v1.ai_routes.CommerceAssistantService.answer", fail_with_secret)
    login = await test_client.post("/api/v1/auth/login", json=test_user_data_in_db)
    csrf = await test_client.get("/api/v1/auth/csrf", cookies=login.cookies)
    response = await test_client.post(
        "/api/v1/ai/chat/stream",
        cookies=login.cookies,
        headers={"X-CSRF-Token": csrf.json()["csrf_token"]},
        json={"question": "Hello"},
    )

    assert response.status_code == 200
    assert "assistant.error" in response.text
    assert "could not complete this request" in response.text
    assert "private diagnostic data" not in response.text
    assert "assistant.completed" not in response.text


async def test_conversation_history_is_empty_owner_scoped_and_restorable(
    test_client: AsyncClient, test_db: AsyncSession, test_user_data_in_db: dict
):
    second_credentials = {
        "email": "second-owner@example.com",
        "password": "SecondOwner123!",
    }
    await UserRepository(test_db).create_user(
        email=second_credentials["email"],
        password_hash=hash_password(second_credentials["password"]),
    )
    await test_db.commit()

    async def authenticate(credentials: dict) -> tuple[dict, str]:
        login = await test_client.post("/api/v1/auth/login", json=credentials)
        assert login.status_code == 200
        csrf = await test_client.get("/api/v1/auth/csrf", cookies=login.cookies)
        assert csrf.status_code == 200
        return login.cookies, csrf.json()["csrf_token"]

    owner_cookies, owner_csrf = await authenticate(test_user_data_in_db)
    other_cookies, other_csrf = await authenticate(second_credentials)

    empty = await test_client.get("/api/v1/ai/conversations", cookies=owner_cookies)
    assert empty.status_code == 200
    assert empty.json() == []

    created = await test_client.post(
        "/api/v1/ai/chat",
        cookies=owner_cookies,
        headers={"X-CSRF-Token": owner_csrf},
        json={"question": "hi", "conversation_id": None},
    )
    assert created.status_code == 200
    created_payload = created.json()
    assert created_payload["intent"] == "GREETING"
    assert created_payload["message_id"]
    conversation_id = created_payload["conversation_id"]

    product = Product(
        name="Contract Test Headphones",
        description="A real catalog fixture",
        sku="CONTRACT-HEADPHONES-1",
        price=499900,
        stock_quantity=4,
        max_purchase_quantity=2,
        is_active=True,
    )
    test_db.add(product)
    await test_db.commit()

    owner_id = UUID(
        (await test_client.get("/api/v1/users/profile", cookies=owner_cookies)).json()["user_id"]
    )
    await CartService(test_db).add_item(owner_id, product.id, 1)
    await OrderService(test_db).checkout(owner_id, "assistant-contract-order", [(product.id, 1)])

    search = await test_client.post(
        "/api/v1/ai/chat",
        cookies=owner_cookies,
        headers={"X-CSRF-Token": owner_csrf},
        json={"question": "show me products under 5000", "conversation_id": conversation_id},
    )
    assert search.status_code == 200
    search_payload = search.json()
    assert search_payload["intent"] == "PRODUCT_SEARCH"
    assert [item["id"] for item in search_payload["result_data"]["products"]] == [str(product.id)]
    assert all(item["price_cents"] <= 500000 for item in search_payload["result_data"]["products"])

    cart_query = await test_client.post(
        "/api/v1/ai/chat",
        cookies=owner_cookies,
        headers={"X-CSRF-Token": owner_csrf},
        json={"question": "what's in my cart?", "conversation_id": conversation_id},
    )
    assert cart_query.status_code == 200
    assert cart_query.json()["result_data"]["cart"]["items"][0]["name"] == product.name

    order_query = await test_client.post(
        "/api/v1/ai/chat",
        cookies=owner_cookies,
        headers={"X-CSRF-Token": owner_csrf},
        json={"question": "where is my last order?", "conversation_id": conversation_id},
    )
    assert order_query.status_code == 200
    assert order_query.json()["intent"] == "ORDER_QUERY"
    assert order_query.json()["result_data"]["orders"][0]["id"]

    policy_query = await test_client.post(
        "/api/v1/ai/chat",
        cookies=owner_cookies,
        headers={"X-CSRF-Token": owner_csrf},
        json={"question": "what is the return policy?", "conversation_id": conversation_id},
    )
    assert policy_query.status_code == 200
    assert policy_query.json()["reason"] == "NO_POLICY_EVIDENCE"
    assert policy_query.json()["citations"] == []

    other_cart = await test_client.post(
        "/api/v1/ai/chat",
        cookies=other_cookies,
        headers={"X-CSRF-Token": other_csrf},
        json={"question": "what's in my cart?"},
    )
    assert other_cart.status_code == 200
    assert other_cart.json()["result_data"]["cart"]["items"] == []
    other_orders = await test_client.post(
        "/api/v1/ai/chat",
        cookies=other_cookies,
        headers={"X-CSRF-Token": other_csrf},
        json={"question": "where is my last order?"},
    )
    assert other_orders.status_code == 200
    assert other_orders.json()["reason"] == "NO_ORDER"

    listed = await test_client.get("/api/v1/ai/conversations", cookies=owner_cookies)
    assert listed.status_code == 200
    assert conversation_id in {item["id"] for item in listed.json()}
    other_list = await test_client.get("/api/v1/ai/conversations", cookies=other_cookies)
    assert other_list.status_code == 200
    assert other_list.json()
    assert conversation_id not in {item["id"] for item in other_list.json()}

    follow_up = await test_client.post(
        "/api/v1/ai/chat",
        cookies=owner_cookies,
        headers={"X-CSRF-Token": owner_csrf},
        json={"question": "what can you do?", "conversation_id": conversation_id},
    )
    assert follow_up.status_code == 200
    assert follow_up.json()["conversation_id"] == conversation_id

    history = await test_client.get(
        f"/api/v1/ai/conversations/{conversation_id}/messages", cookies=owner_cookies
    )
    assert history.status_code == 200
    assert [message["role"] for message in history.json()] == ["user", "assistant"] * 6

    foreign_history = await test_client.get(
        f"/api/v1/ai/conversations/{conversation_id}/messages", cookies=other_cookies
    )
    assert foreign_history.status_code == 404
    foreign_chat = await test_client.post(
        "/api/v1/ai/chat",
        cookies=other_cookies,
        headers={"X-CSRF-Token": other_csrf},
        json={"question": "hi", "conversation_id": conversation_id},
    )
    assert foreign_chat.status_code == 404
    invalid_id = await test_client.get(
        "/api/v1/ai/conversations/not-a-uuid/messages", cookies=owner_cookies
    )
    assert invalid_id.status_code == 422


async def test_policy_answer_uses_server_owned_fixture_and_returns_provenance(
    test_client: AsyncClient,
    test_db: AsyncSession,
    test_user_data_in_db: dict,
    monkeypatch,
):
    from src.core.config import settings

    monkeypatch.setattr(settings, "ai_provider", "deterministic")
    source_id = await KnowledgeIngestionService(test_db).publish(
        source_key="test-returns-policy",
        title="ShopSmart Returns Policy (Test Fixture)",
        category="returns",
        content=(
            "ShopSmart return policy: eligible purchases may be returned within 30 days. "
            "Products must be unused and the purchase receipt must be provided."
        ),
    )
    login = await test_client.post("/api/v1/auth/login", json=test_user_data_in_db)
    csrf = await test_client.get("/api/v1/auth/csrf", cookies=login.cookies)

    response = await test_client.post(
        "/api/v1/ai/chat",
        cookies=login.cookies,
        headers={"X-CSRF-Token": csrf.json()["csrf_token"]},
        json={"question": "What is the return policy?"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["answerable"] is True
    assert payload["citations"]
    assert payload["citations"][0]["document_id"] == str(source_id)
    assert payload["citations"][0]["knowledge_version_id"]
    assert payload["citations"][0]["source_label"] == "ShopSmart Returns Policy (Test Fixture)"
