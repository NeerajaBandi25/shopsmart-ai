"""Checkout endpoint and PostgreSQL inventory-locking proofs."""

import asyncio
from datetime import datetime
from typing import AsyncGenerator
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.api.v1 import order_routes
from src.api.v1.deps import get_db
from src.core.exceptions import AppException, ConflictError
from src.models.order import Order
from src.models.payment import Payment
from src.models.product import Product
from src.models.session import Session
from src.models.user import User
from src.services.order_service import OrderService
from src.services.payment_provider import CheckoutSession, get_payment_provider
from src.services.promotion_service import PromotionService


class FakePaymentProvider:
    """Explicit integration-test provider; never selectable through app configuration."""

    name = "fake-test"

    def is_configured(self) -> bool:
        return True

    def validate_checkout_configuration(self) -> None:
        return None

    async def create_checkout_session(self, **kwargs) -> CheckoutSession:
        order_id = kwargs["order_id"]
        return CheckoutSession(f"cs_test_{order_id}", f"https://checkout.test/{order_id}")

    def verify_webhook(self, raw_body: bytes, signature: str | None):
        raise NotImplementedError

    async def refund(self, payment_id: str, amount_cents: int | None, idempotency_key: str):
        raise NotImplementedError


class DisabledPaymentProvider(FakePaymentProvider):
    def is_configured(self) -> bool:
        return False


class InvalidCheckoutConfigurationProvider(FakePaymentProvider):
    def validate_checkout_configuration(self) -> None:
        raise AppException("Invalid sandbox return URL", 503, "payment_config_invalid")


DELIVERY_ADDRESS = {
    "recipient_name": "Portfolio Shopper",
    "phone": "+91 98765 43210",
    "address_line1": "12 Example Road",
    "address_line2": None,
    "city": "Bengaluru",
    "region": "Karnataka",
    "postal_code": "560001",
    "country_code": "IN",
}


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
    app.dependency_overrides[get_payment_provider] = lambda: FakePaymentProvider()
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


def _product(
    product_id: UUID,
    sku: str,
    *,
    active: bool = True,
    image_url: str | None = None,
    image_alt: str | None = None,
) -> Product:
    return Product(
        id=product_id,
        name=f"Product {sku}",
        sku=sku,
        price=1250,
        stock_quantity=8,
        max_purchase_quantity=4,
        is_active=active,
        image_url=image_url,
        image_alt=image_alt,
    )


class TestCheckoutEndpoints:
    @pytest.mark.parametrize("total_cents", [0, 49, 100_000_000])
    async def test_unsupported_payable_total_fails_before_order_or_stock_reservation(
        self, test_db: AsyncSession, monkeypatch, total_cents: int
    ):
        user_id = uuid4()
        product_id = uuid4()
        test_db.add_all(
            [
                User(
                    id=user_id,
                    email=f"zero-payment-{user_id}@example.com",
                    password_hash="unused",
                ),
                _product(product_id, "ZERO-PAYABLE-TOTAL"),
            ]
        )
        await test_db.commit()

        async def zero_total_quote(self, user_id, items, coupon_code):
            return {
                "subtotal": 1250,
                "coupon_code": coupon_code,
                "coupon_evaluation": None,
                "applied_promotions": [],
                "discount_total_cents": 1250,
                "total_cents": total_cents,
                "currency": "INR",
                "evaluated_at": "2026-10-05T00:00:00+00:00",
            }

        monkeypatch.setattr(PromotionService, "quote", zero_total_quote)
        with pytest.raises(AppException, match="not supported by hosted checkout") as error:
            await OrderService(test_db).checkout(
                user_id,
                "zero-total-checkout",
                [(product_id, 1)],
                initial_status="pending_payment",
            )

        assert error.value.error_code == "hosted_checkout_amount_unsupported"
        assert await test_db.scalar(select(func.count()).select_from(Order)) == 0
        product = await test_db.get(Product, product_id)
        assert product.stock_quantity == 8

    async def test_unconfigured_provider_fails_before_order_or_stock_reservation(
        self, order_client: AsyncClient, test_db: AsyncSession
    ):
        _, cookies, csrf_headers = await _create_session(test_db)
        product_id = uuid4()
        product = _product(product_id, "NO-PAYMENT-PROVIDER")
        test_db.add(product)
        await test_db.commit()
        app = order_client._transport.app
        app.dependency_overrides[get_payment_provider] = lambda: DisabledPaymentProvider()
        response = await order_client.post(
            "/api/v1/orders/checkout",
            json={
                "items": [{"product_id": str(product_id), "quantity": 1}],
                "delivery_address": DELIVERY_ADDRESS,
            },
            cookies=cookies,
            headers={**csrf_headers, "Idempotency-Key": "payment-disabled"},
        )
        assert response.status_code == 503
        assert response.json()["error_code"] == "payment_provider_unavailable"
        await test_db.refresh(product)
        assert product.stock_quantity == 8
        assert await test_db.scalar(select(func.count(Order.id))) == 0

    async def test_invalid_checkout_configuration_fails_before_order_or_reservation(
        self, order_client: AsyncClient, test_db: AsyncSession
    ):
        _, cookies, csrf_headers = await _create_session(test_db)
        product_id = uuid4()
        product = _product(product_id, "INVALID-CHECKOUT-CONFIG")
        test_db.add(product)
        await test_db.commit()
        app = order_client._transport.app
        app.dependency_overrides[
            get_payment_provider
        ] = lambda: InvalidCheckoutConfigurationProvider()

        response = await order_client.post(
            "/api/v1/orders/checkout",
            json={
                "items": [{"product_id": str(product_id), "quantity": 1}],
                "delivery_address": DELIVERY_ADDRESS,
            },
            cookies=cookies,
            headers={**csrf_headers, "Idempotency-Key": "invalid-payment-config"},
        )

        assert response.status_code == 503
        assert response.json()["error_code"] == "payment_config_invalid"
        await test_db.refresh(product)
        assert product.stock_quantity == 8
        assert await test_db.scalar(select(func.count(Order.id))) == 0

    async def test_checkout_requires_auth_csrf_and_idempotency_key(
        self, order_client: AsyncClient, test_db: AsyncSession
    ):
        _, cookies, headers = await _create_session(test_db)
        payload = {
            "items": [{"product_id": str(uuid4()), "quantity": 1}],
            "delivery_address": DELIVERY_ADDRESS,
        }

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
        product = _product(
            product_id,
            "API-ORDER-1",
            image_url="/images/products/portfolio/test-order.png",
            image_alt="Original order illustration",
        )
        test_db.add(product)
        await test_db.commit()
        request_headers = {**csrf_headers, "Idempotency-Key": "api-retry"}
        payload = {
            "items": [{"product_id": str(product_id), "quantity": 2}],
            "delivery_address": DELIVERY_ADDRESS,
        }

        first = await order_client.post(
            "/api/v1/orders/checkout", json=payload, cookies=cookies, headers=request_headers
        )
        assert first.status_code == 201
        first_data = first.json()
        assert first_data["status"] == "pending_payment"
        assert first_data["payment_status"] == "requires_action"
        assert first_data["checkout_url"].startswith("https://checkout.test/")
        assert first_data["total_cents"] == 2500
        assert first_data["items"][0]["unit_price_cents"] == 1250
        assert first_data["delivery_address"] == DELIVERY_ADDRESS
        assert (
            first_data["items"][0]["product_image_url"]
            == "/images/products/portfolio/test-order.png"
        )
        assert first_data["items"][0]["product_image_alt"] == "Original order illustration"
        assert "price" not in payload["items"][0]

        product.name = "Changed catalog name"
        product.price = 4000
        product.image_url = "/images/products/portfolio/changed.png"
        product.image_alt = "Changed catalog illustration"
        await test_db.commit()
        replay = await order_client.post(
            "/api/v1/orders/checkout", json=payload, cookies=cookies, headers=request_headers
        )
        assert replay.status_code == 201
        assert replay.json() == first_data

        changed_payload = {
            "items": [{"product_id": str(product_id), "quantity": 1}],
            "delivery_address": DELIVERY_ADDRESS,
        }
        conflict = await order_client.post(
            "/api/v1/orders/checkout",
            json=changed_payload,
            cookies=cookies,
            headers=request_headers,
        )
        assert conflict.status_code == 409
        assert conflict.json()["error_code"] == "idempotency_conflict"
        changed_address = {**payload, "delivery_address": {**DELIVERY_ADDRESS, "city": "Mysuru"}}
        address_conflict = await order_client.post(
            "/api/v1/orders/checkout",
            json=changed_address,
            cookies=cookies,
            headers=request_headers,
        )
        assert address_conflict.status_code == 409
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
                ],
                "delivery_address": DELIVERY_ADDRESS,
            },
            cookies=cookies,
            headers=headers,
        )
        assert duplicate.status_code == 422

        missing = await order_client.post(
            "/api/v1/orders/checkout",
            json={
                "items": [{"product_id": str(uuid4()), "quantity": 1}],
                "delivery_address": DELIVERY_ADDRESS,
            },
            cookies=cookies,
            headers={**headers, "Idempotency-Key": "missing"},
        )
        assert missing.status_code == 404

        inactive = await order_client.post(
            "/api/v1/orders/checkout",
            json={
                "items": [{"product_id": str(inactive_id), "quantity": 1}],
                "delivery_address": DELIVERY_ADDRESS,
            },
            cookies=cookies,
            headers={**headers, "Idempotency-Key": "inactive"},
        )
        assert inactive.status_code == 409

        stock = await test_db.scalar(select(Product.stock_quantity).where(Product.id == active_id))
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
                "items": [{"product_id": str(product_id), "quantity": 1, "price": 1}],
                "delivery_address": DELIVERY_ADDRESS,
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
                    subtotal_cents=100,
                    discount_total_cents=0,
                    total_cents=100,
                    promotion_snapshot=[],
                    created_at=datetime(2026, 1, 1),
                ),
                Order(
                    user_id=owner_id,
                    idempotency_key="new",
                    request_hash="b" * 64,
                    status="placed",
                    subtotal_cents=200,
                    discount_total_cents=0,
                    total_cents=200,
                    promotion_snapshot=[],
                    created_at=datetime(2026, 1, 2),
                ),
                Order(
                    user_id=other_id,
                    idempotency_key="other",
                    request_hash="c" * 64,
                    status="placed",
                    subtotal_cents=999,
                    discount_total_cents=0,
                    total_cents=999,
                    promotion_snapshot=[],
                ),
            ]
        )
        await test_db.commit()

        response = await order_client.get("/api/v1/orders", cookies=cookies)
        assert response.status_code == 200
        assert [row["total_cents"] for row in response.json()] == [200, 100]


@pytest.mark.asyncio
async def test_payment_retry_reuses_owner_order_and_payment_record(order_client, test_db):
    user_id, cookies, csrf = await _create_session(test_db)
    order = Order(
        user_id=user_id,
        idempotency_key="retry-existing-order",
        request_hash="d" * 64,
        status="pending_payment",
        subtotal_cents=1200,
        discount_total_cents=0,
        total_cents=1200,
        promotion_snapshot=[],
    )
    test_db.add(order)
    await test_db.flush()
    payment = Payment(
        order_id=order.id,
        user_id=user_id,
        provider="fake-test",
        amount_cents=1200,
        currency="INR",
        status="failed",
        session_generation=0,
    )
    test_db.add(payment)
    await test_db.commit()

    response = await order_client.post(
        f"/api/v1/orders/{order.id}/payment/retry", cookies=cookies, headers=csrf
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == str(order.id)
    assert payload["payment_status"] == "requires_action"
    assert payload["checkout_url"] == f"https://checkout.test/{order.id}"
    assert (
        await test_db.scalar(
            select(func.count()).select_from(Order).where(Order.user_id == user_id)
        )
        == 1
    )
    assert (
        await test_db.scalar(
            select(func.count()).select_from(Payment).where(Payment.order_id == order.id)
        )
        == 1
    )


@pytest.mark.asyncio
async def test_pending_payment_order_limit_prevents_additional_reservations(order_client, test_db):
    user_id, cookies, csrf = await _create_session(test_db)
    test_db.add_all(
        [
            Order(
                user_id=user_id,
                idempotency_key=f"pending-{index}",
                request_hash=str(index) * 64,
                status="pending_payment",
                subtotal_cents=100,
                discount_total_cents=0,
                total_cents=100,
                promotion_snapshot=[],
            )
            for index in range(3)
        ]
    )
    await test_db.commit()

    response = await order_client.post(
        "/api/v1/orders/checkout",
        cookies=cookies,
        headers={**csrf, "Idempotency-Key": "one-more-pending"},
        json={
            "items": [{"product_id": str(uuid4()), "quantity": 1}],
            "delivery_address": DELIVERY_ADDRESS,
        },
    )

    assert response.status_code == 409
    assert response.json()["error_code"] == "pending_payment_limit"
    assert (
        await test_db.scalar(
            select(func.count()).select_from(Order).where(Order.user_id == user_id)
        )
        == 3
    )


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
                User(
                    id=user_id, email=f"concurrency-{user_id}@example.com", password_hash="unused"
                ),
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


async def test_concurrent_pending_orders_cannot_exceed_per_user_limit(pg_checkout_factory):
    factory = pg_checkout_factory
    user_id = uuid4()
    product_id = uuid4()
    async with factory() as setup:
        setup.add_all(
            [
                User(
                    id=user_id,
                    email=f"pending-limit-{user_id}@example.com",
                    password_hash="unused",
                ),
                Product(
                    id=product_id,
                    name="Pending limit item",
                    sku=f"PG-LIMIT-{product_id}",
                    price=950,
                    stock_quantity=3,
                    max_purchase_quantity=1,
                    is_active=True,
                ),
            ]
        )
        await setup.flush()
        setup.add_all(
            [
                Order(
                    user_id=user_id,
                    idempotency_key=f"preexisting-{index}",
                    request_hash=str(index) * 64,
                    status="pending_payment",
                    subtotal_cents=100,
                    discount_total_cents=0,
                    total_cents=100,
                    promotion_snapshot=[],
                )
                for index in range(2)
            ]
        )
        await setup.commit()

    async def attempt(key: str) -> str:
        async with factory() as session:
            try:
                await OrderService(session).checkout(
                    user_id, key, [(product_id, 1)], initial_status="pending_payment"
                )
                return "created"
            except ConflictError as exc:
                await session.rollback()
                return exc.error_code

    outcomes = await asyncio.gather(attempt("parallel-pending-a"), attempt("parallel-pending-b"))
    async with factory() as check:
        active_orders = await check.scalar(
            select(func.count())
            .select_from(Order)
            .where(Order.user_id == user_id, Order.status == "pending_payment")
        )
        remaining_stock = await check.scalar(
            select(Product.stock_quantity).where(Product.id == product_id)
        )
    assert sorted(outcomes) == ["created", "pending_payment_limit"]
    assert active_orders == 3
    assert remaining_stock == 2


async def test_postgres_idempotency_preserves_authoritative_order_price(pg_checkout_factory):
    factory = pg_checkout_factory
    user_id = uuid4()
    product_id = uuid4()
    async with factory() as setup:
        setup.add_all(
            [
                User(
                    id=user_id, email=f"idempotency-{user_id}@example.com", password_hash="unused"
                ),
                Product(
                    id=product_id,
                    name="Authoritative price item",
                    sku=f"PG-{product_id}",
                    price=1549,
                    stock_quantity=3,
                    max_purchase_quantity=3,
                    is_active=True,
                ),
            ]
        )
        await setup.commit()

    async with factory() as checkout:
        original = await OrderService(checkout).checkout(user_id, "retry-once", [(product_id, 1)])
        original_order_id = original.id
        assert original.total_cents == 1549

    async with factory() as update:
        product = await update.get(Product, product_id)
        product.price = 2999
        await update.commit()

    async with factory() as retry:
        replay = await OrderService(retry).checkout(user_id, "retry-once", [(product_id, 1)])
        assert replay.id == original_order_id
        assert replay.total_cents == 1549

    async with factory() as check:
        stock = await check.scalar(select(Product.stock_quantity).where(Product.id == product_id))
        order_count = await check.scalar(
            select(func.count()).select_from(Order).where(Order.user_id == user_id)
        )
        persisted = await check.scalar(select(Order).where(Order.id == original_order_id))
        assert stock == 2
        assert order_count == 1
        assert persisted.subtotal_cents == 1549
        assert persisted.total_cents == 1549
        assert persisted.items[0].unit_price_cents == 1549


async def test_postgres_checkout_database_failure_rolls_back_order_and_stock(pg_checkout_factory):
    factory = pg_checkout_factory
    engine = factory.kw["bind"]
    user_id = uuid4()
    product_id = uuid4()
    suffix = uuid4().hex
    sku = f"PG-ROLLBACK-{suffix}"
    function_name = f"shopsmart_fail_order_item_{suffix}"
    trigger_name = f"shopsmart_fail_order_item_{suffix}"
    async with factory() as setup:
        setup.add_all(
            [
                User(id=user_id, email=f"rollback-{user_id}@example.com", password_hash="unused"),
                Product(
                    id=product_id,
                    name="Rollback item",
                    sku=sku,
                    price=2375,
                    stock_quantity=2,
                    max_purchase_quantity=2,
                    is_active=True,
                ),
            ]
        )
        await setup.commit()

    async with engine.begin() as connection:
        await connection.execute(
            text(
                f"CREATE FUNCTION public.{function_name}() RETURNS trigger LANGUAGE plpgsql "
                "AS $$ BEGIN RAISE EXCEPTION 'injected persistence failure'; END $$"
            )
        )
        await connection.execute(
            text(
                f"CREATE TRIGGER {trigger_name} BEFORE INSERT ON public.order_items "
                f"FOR EACH ROW WHEN (NEW.product_sku = '{sku}') "
                f"EXECUTE FUNCTION public.{function_name}()"
            )
        )

    try:
        async with factory() as checkout:
            with pytest.raises(DBAPIError, match="injected persistence failure"):
                await OrderService(checkout).checkout(user_id, "rollback-order", [(product_id, 1)])
            await checkout.rollback()

        async with factory() as check:
            stock = await check.scalar(
                select(Product.stock_quantity).where(Product.id == product_id)
            )
            order_count = await check.scalar(
                select(func.count()).select_from(Order).where(Order.user_id == user_id)
            )
            assert stock == 2
            assert order_count == 0
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                text(f"DROP TRIGGER IF EXISTS {trigger_name} ON public.order_items")
            )
            await connection.execute(text(f"DROP FUNCTION IF EXISTS public.{function_name}()"))
