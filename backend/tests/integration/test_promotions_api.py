"""Authenticated and CSRF-protected coupon API tests."""

from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator
from uuid import UUID, uuid4

import pytest_asyncio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1 import cart_routes
from src.api.v1.deps import get_db
from src.core.exceptions import AppException
from src.models.product import Product
from src.models.promotion import Promotion
from src.models.session import Session
from src.models.user import User
from src.services.cart_service import CartService


@pytest_asyncio.fixture
async def promotions_client(test_db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    app = FastAPI()
    app.include_router(cart_routes.router, prefix="/api/v1")

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message, "error_code": exc.error_code},
        )

    async def override_db():
        yield test_db

    app.dependency_overrides[get_db] = override_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="https://promotions.test"
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
                user_agent="promotion-tests",
                csrf_token="valid-csrf-token",
                last_activity=datetime.now(timezone.utc),
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


async def test_coupon_routes_require_authentication_and_csrf(
    promotions_client: AsyncClient, test_db: AsyncSession
):
    unauthenticated = await promotions_client.post("/api/v1/cart/coupon", json={"code": "SAVE20"})
    user_id, cookies, _ = await _create_session(test_db)
    missing_csrf = await promotions_client.post(
        "/api/v1/cart/coupon", json={"code": "SAVE20"}, cookies=cookies
    )

    assert unauthenticated.status_code == 401
    assert missing_csrf.status_code == 403


async def test_coupon_apply_returns_authoritative_cart_and_bad_code_preserves_state(
    promotions_client: AsyncClient, test_db: AsyncSession
):
    user_id, cookies, headers = await _create_session(test_db)
    product = Product(
        name="Laptop",
        sku="PROMO-API-1",
        price=1299,
        stock_quantity=5,
        max_purchase_quantity=3,
        is_active=True,
    )
    now = datetime.now(timezone.utc)
    promotion = Promotion(
        code="SAVE20",
        name="Twenty percent",
        promotion_type="percentage",
        value=20,
        starts_at=now - timedelta(days=1),
        ends_at=now + timedelta(days=1),
        active=True,
        scope_type="all",
    )
    test_db.add_all([product, promotion])
    await test_db.commit()
    await CartService(test_db).add_item(user_id, product.id, 1)

    applied = await promotions_client.post(
        "/api/v1/cart/coupon",
        json={"code": " save20 "},
        cookies=cookies,
        headers=headers,
    )
    invalid = await promotions_client.post(
        "/api/v1/cart/coupon",
        json={"code": "NOTREAL"},
        cookies=cookies,
        headers=headers,
    )
    current = await promotions_client.get("/api/v1/cart", cookies=cookies)

    assert applied.status_code == 200
    assert applied.json()["coupon_code"] == "SAVE20"
    assert applied.json()["subtotal"] == 1299
    assert applied.json()["discount_total_cents"] == 260
    assert applied.json()["total_cents"] == 1039
    assert invalid.status_code == 422
    assert invalid.json()["error_code"] == "invalid_coupon"
    assert current.json()["coupon_code"] == "SAVE20"
    assert current.json()["total_cents"] == 1039


async def test_coupon_payload_rejects_extra_fields(
    promotions_client: AsyncClient, test_db: AsyncSession
):
    _, cookies, headers = await _create_session(test_db)

    response = await promotions_client.post(
        "/api/v1/cart/coupon",
        json={"code": "SAVE20", "discount_cents": 999999},
        cookies=cookies,
        headers=headers,
    )

    assert response.status_code == 422
