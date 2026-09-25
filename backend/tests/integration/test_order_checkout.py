"""Checkout endpoint and PostgreSQL inventory-locking proofs."""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.api.v1 import order_routes
from src.api.v1.deps import get_db
from src.core.exceptions import AppException, ConflictError
from src.models.order import Order
from src.models.product import Product
from src.models.session import Session
from src.models.user import User
from src.services.order_service import OrderService


@pytest_asyncio.fixture
async def order_client(test_db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    app = FastAPI()
    app.include_router(order_routes.router, prefix="/api/v1")

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.message,
                "status_code": exc.status_code,
                "error_code": exc.error_code,
            },
        )

    async def override_db():
        yield test_db

    app.dependency_overrides[get_db] = override_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="https://orders.test"
    ) as client:
        yield client


async def _create_session(test_db: AsyncSession) -> tuple[UUID, dict[str, str], dict[str, str]]:
    user_id = uuid4()
    session_id = uuid4()
    test_db.add_all(
        [
            User(id=user_id, email=f"{user_id}@example.com", password_hash="unused"),
            Session(
                id=session_id,
                user_id=user_id,
                ip_address="127.0.0.1",
                user_agent="checkout-tests",
                csrf_token="valid-csrf-token",
                last_activity=datetime.utcnow(),
                is_active=True,
            ),
        ]
    )
    await test_db.commit()
    return (
        user_id,
        {"session_id": str(session_id)},
        {"X-CSRF-Token": "valid-csrf-token"},
    )


def _product(product_id: UUID, sku: str, *, active: bool = True) -> Product:
    return Product(
        id=product_id,
        name=f"Product {sku}",
        sku=sku,
        price=1250,
        stock_quantity=8,
        max_purchase_quantity=4,
        is_active=active,
    )


class TestCheckoutEndpoints:
    async def test_checkout_requires_auth_csrf_and_idempotency_key(
        self, order_client: AsyncClient, test_db: AsyncSession
    ):
        _, cookies, headers = await _create_session(test_db)
        payload = {"items": [{"product_id": str(uuid4()), "quantity": 1}]}

        unauthenticated = await order_client.post(
            "/api/v1/orders/checkout", json=payload, headers={"Idempotency-Key": "x"}
        )
        assert unauthenticated.status_code == 401

        missing_csrf = await order_client.post(
            "/api/v1/orders/checkout",
            json=payload,
            cookies=cookies,
            headers={"Idempotency-Key": "x"},
        )
        assert missing_csrf.status_code == 403

        missing_key = await order_client.post(
            "/api/v1/orders/checkout", json=payload, cookies=cookies, headers=headers
        )
        assert missing_key.status_code == 422

    async def test_checkout_replay_snapshots_conflict_and_server_prices(
        self, order_client: AsyncClient, test_db: AsyncSession
    ):
        user_id, cookies, csrf_headers = await _create_session(test_db)
        product_id = uuid4()
        product = _product(product_id, "API-ORDER-1")
        test_db.add(product)
        await test_db.commit()
        request_headers = {**csrf_headers, "Idempotency-Key": "api-retry"}
        payload = {"items": [{"product_id": str(product_id), "quantity": 2}]}

        first = await order_client.post(
            "/api/v1/orders/checkout", json=payload, cookies=cookies, headers=request_headers
        )
        assert first.status_code == 201
        first_data = first.json()
        assert first_data["total_cents"] == 2500
        assert first_data["items"][0]["unit_price_cents"] == 1250
        assert "price" not in payload["items"][0]

        product.name = "Changed catalog name"
        product.price = 4000
        await test_db.commit()
        replay = await order_client.post(
            "/api/v1/orders/checkout", json=payload, cookies=cookies, headers=request_headers
        )
        assert replay.status_code == 201
        assert replay.json() == first_data

        changed_payload = {"items": [{"product_id": str(product_id), "quantity": 1}]}
        conflict = await order_client.post(
            "/api/v1/orders/checkout",
            json=changed_payload,
            cookies=cookies,
            headers=request_headers,
        )
        assert conflict.status_code == 409
        assert conflict.json()["error_code"] == "idempotency_conflict"
        assert user_id

    async def test_checkout_rejects_invalid_lines_without_stock_changes(
        self, order_client: AsyncClient, test_db: AsyncSession
    ):
        _, cookies, csrf_headers = await _create_session(test_db)
        active_id = uuid4()
        inactive_id = uuid4()
        test_db.add_all(
            [_product(active_id, "API-ACTIVE"), _product(inactive_id, "API-INACTIVE", active=False)]
        )
        await test_db.commit()
        headers = {**csrf_headers, "Idempotency-Key": "invalid-lines"}

        duplicate = await order_client.post(
            "/api/v1/orders/checkout",
            json={
                "items": [
                    {"product_id": str(active_id), "quantity": 1},
                    {"product_id": str(active_id), "quantity": 1},
                ]
            },
            cookies=cookies,
            headers=headers,
        )
        assert duplicate.status_code == 422

        missing = await order_client.post(
            "/api/v1/orders/checkout",
            json={"items": [{"product_id": str(uuid4()), "quantity": 1}]},
            cookies=cookies,
            headers={**headers, "Idempotency-Key": "missing"},
        )
        assert missing.status_code == 404

        inactive = await order_client.post(
            "/api/v1/orders/checkout",
            json={"items": [{"product_id": str(inactive_id), "quantity": 1}]},
            cookies=cookies,
            headers={**headers, "Idempotency-Key": "inactive"},
        )
        assert inactive.status_code == 409

        stock = await test_db.scalar(
            select(Product.stock_quantity).where(Product.id == active_id)
        )
        assert stock == 8

    async def test_checkout_rejects_client_supplied_prices(
        self, order_client: AsyncClient, test_db: AsyncSession
    ):
        _, cookies, csrf_headers = await _create_session(test_db)
        product_id = uuid4()
        test_db.add(_product(product_id, "NO-CLIENT-PRICE"))
        await test_db.commit()

        response = await order_client.post(
            "/api/v1/orders/checkout",
            json={
                "items": [{"product_id": str(product_id), "quantity": 1, "price": 1}]
            },
            cookies=cookies,
            headers={**csrf_headers, "Idempotency-Key": "untrusted-price"},
        )

        assert response.status_code == 422

    async def test_history_is_user_scoped_and_newest_first(
        self, order_client: AsyncClient, test_db: AsyncSession
    ):
        owner_id, cookies, _ = await _create_session(test_db)
        other_id, _, _ = await _create_session(test_db)
        test_db.add_all(
            [
                Order(
                    user_id=owner_id,
                    idempotency_key="old",
                    request_hash="a" * 64,
                    status="placed",
                    total_cents=100,
                    created_at=datetime(2026, 1, 1),
                ),
                Order(
                    user_id=owner_id,
                    idempotency_key="new",
                    request_hash="b" * 64,
                    status="placed",
                    total_cents=200,
                    created_at=datetime(2026, 1, 2),
                ),
                Order(
                    user_id=other_id,
                    idempotency_key="other",
                    request_hash="c" * 64,
                    status="placed",
                    total_cents=999,
                ),
            ]
        )
        await test_db.commit()

        response = await order_client.get("/api/v1/orders", cookies=cookies)
        assert response.status_code == 200
        assert [row["total_cents"] for row in response.json()] == [200, 100]


def _pg_test_url() -> str:
    from src.core.config import settings

    url = settings.database_url
    if "_test" not in url:
        parts = url.rsplit("/", 1)
        if len(parts) == 2:
            url = f"{parts[0]}/{parts[1]}_test"
    return url.replace("@localhost", "@127.0.0.1")


@pytest_asyncio.fixture
async def pg_checkout_factory():
    url = _pg_test_url()
    if not url.startswith("postgresql"):
        pytest.skip("PostgreSQL DATABASE_URL not configured; skipping checkout lock proof")
    try:
        engine = create_async_engine(url, echo=False)
        async with engine.connect():
            pass
    except Exception as exc:  # pragma: no cover - environment-dependent
        pytest.skip(f"PostgreSQL unavailable: {exc}")
    from src.models.base import Base

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
    except Exception as exc:  # pragma: no cover - environment-dependent
        await engine.dispose()
        pytest.skip(f"PostgreSQL test schema unavailable: {exc}")
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield factory
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def test_concurrent_checkouts_do_not_oversell(pg_checkout_factory):
    factory = pg_checkout_factory
    user_id = uuid4()
    product_id = uuid4()
    async with factory() as setup:
        setup.add_all(
            [
                User(id=user_id, email=f"concurrency-{user_id}@example.com", password_hash="unused"),
                Product(
                    id=product_id,
                    name="Last unit",
                    sku=f"PG-{product_id}",
                    price=950,
                    stock_quantity=1,
                    max_purchase_quantity=1,
                    is_active=True,
                ),
            ]
        )
        await setup.commit()

    async def attempt(key: str) -> str:
        async with factory() as session:
            try:
                await OrderService(session).checkout(user_id, key, [(product_id, 1)])
                return "placed"
            except ConflictError:
                await session.rollback()
                return "rejected"

    outcomes = await asyncio.gather(attempt("parallel-a"), attempt("parallel-b"))
    async with factory() as check:
        remaining_stock = await check.scalar(
            select(Product.stock_quantity).where(Product.id == product_id)
        )
        order_count = await check.scalar(
            select(func.count()).select_from(Order).where(Order.user_id == user_id)
        )
    assert sorted(outcomes) == ["placed", "rejected"]
    assert remaining_stock == 0
    assert order_count == 1