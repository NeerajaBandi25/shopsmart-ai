"""Focused tests for cart persistence and business rules."""

import logging
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import AppException, ValidationError
from src.core.observability import JsonLogFormatter
from src.models.cart import Cart, CartItem
from src.models.product import Product
from src.models.promotion import Promotion
from src.services.cart_service import CartService


async def _product(db: AsyncSession, *, active: bool = True) -> Product:
    product = Product(
        name="Desk Lamp",
        description=None,
        sku=f"LAMP-{uuid4().hex[:8]}",
        price=1299,
        stock_quantity=8,
        max_purchase_quantity=3,
        is_active=active,
    )
    db.add(product)
    await db.flush()
    return product


async def test_empty_cart_returns_zero_subtotal(test_db: AsyncSession):
    cart = await CartService(test_db).get_cart(uuid4())

    assert cart == {
        "items": [],
        "subtotal": 0,
        "currency": "INR",
        "coupon_code": None,
        "coupon_evaluation": None,
        "applied_promotions": [],
        "discount_total_cents": 0,
        "total_cents": 0,
    }


async def test_add_increments_line_and_calculates_server_totals(test_db: AsyncSession):
    user_id = uuid4()
    product = await _product(test_db)
    service = CartService(test_db)

    await service.add_item(user_id, product.id, 1)
    cart = await service.add_item(user_id, product.id, 2)

    assert cart["items"] == [
        {
            "product_id": product.id,
            "name": product.name,
            "sku": product.sku,
            "image_url": None,
            "image_alt": None,
            "unit_price": 1299,
            "quantity": 3,
            "line_total": 3897,
            "stock_quantity": 8,
            "max_purchase_quantity": 3,
        }
    ]
    assert cart["subtotal"] == 3897
    assert cart["currency"] == "INR"
    assert cart["discount_total_cents"] == 0
    assert cart["total_cents"] == 3897


async def test_add_can_defer_commit_for_atomic_assistant_persistence(
    test_db: AsyncSession, monkeypatch
):
    product = await _product(test_db)
    commit = AsyncMock()
    monkeypatch.setattr(test_db, "commit", commit)

    await CartService(test_db).add_item(uuid4(), product.id, 1, commit=False)

    commit.assert_not_awaited()


async def test_set_quantity_is_exact_and_remove_clears_line(test_db: AsyncSession):
    user_id = uuid4()
    product = await _product(test_db)
    service = CartService(test_db)

    await service.add_item(user_id, product.id, 2)
    updated = await service.set_item_quantity(user_id, product.id, 1)
    removed = await service.remove_item(user_id, product.id)

    assert updated["items"][0]["quantity"] == 1
    assert updated["subtotal"] == 1299
    assert removed["items"] == []
    assert removed["subtotal"] == removed["total_cents"] == 0


@pytest.mark.parametrize("quantity", [4, 9])
async def test_add_rejects_quantity_above_limit_or_stock(test_db: AsyncSession, quantity: int):
    product = await _product(test_db)

    with pytest.raises(ValidationError):
        await CartService(test_db).add_item(uuid4(), product.id, quantity)


async def test_increment_rejects_total_above_purchase_limit(test_db: AsyncSession):
    product = await _product(test_db)
    service = CartService(test_db)
    user_id = uuid4()
    await service.add_item(user_id, product.id, 2)

    with pytest.raises(ValidationError):
        await service.add_item(user_id, product.id, 2)

    cart = await service.get_cart(user_id)
    assert cart["items"][0]["quantity"] == 2


async def test_mutation_rejects_inactive_and_missing_products(test_db: AsyncSession):
    inactive = await _product(test_db, active=False)
    service = CartService(test_db)

    with pytest.raises(HTTPException) as inactive_error:
        await service.add_item(uuid4(), inactive.id, 1)
    with pytest.raises(HTTPException) as missing_error:
        await service.add_item(uuid4(), uuid4(), 1)

    assert inactive_error.value.status_code == 404
    assert missing_error.value.status_code == 404


async def test_cart_rows_are_isolated_by_user(test_db: AsyncSession):
    product = await _product(test_db)
    first_user, second_user = uuid4(), uuid4()
    service = CartService(test_db)
    await service.add_item(first_user, product.id, 1)
    await service.add_item(second_user, product.id, 2)

    first_cart = await service.get_cart(first_user)
    second_cart = await service.get_cart(second_user)
    cart_rows = (await test_db.execute(select(Cart))).scalars().all()
    item_rows = (await test_db.execute(select(CartItem))).scalars().all()

    assert first_cart["items"][0]["quantity"] == 1
    assert second_cart["items"][0]["quantity"] == 2
    assert len(cart_rows) == 2
    assert len(item_rows) == 2


async def test_cart_applies_current_automatic_promotion_from_server_prices(test_db: AsyncSession):
    user_id = uuid4()
    product = await _product(test_db)
    product.category = "laptops"
    now = datetime.now(timezone.utc)
    promotion = Promotion(
        name="Laptop offer",
        promotion_type="percentage",
        value=10,
        starts_at=now - timedelta(days=1),
        ends_at=now + timedelta(days=1),
        active=True,
        scope_type="category",
        scope_category="laptops",
    )
    test_db.add(promotion)
    await test_db.flush()
    service = CartService(test_db)

    cart = await service.add_item(user_id, product.id, 1)

    assert cart["subtotal"] == 1299
    assert cart["discount_total_cents"] == 130
    assert cart["total_cents"] == 1169
    assert cart["applied_promotions"][0]["promotion_id"] == str(promotion.id)


async def test_coupon_normalizes_code_and_invalid_attempt_preserves_existing(
    test_db: AsyncSession, monkeypatch
):
    promotion_logs = []

    def capture_promotion_log(message, *, extra):
        promotion_logs.append(
            logging.makeLogRecord(
                {"name": "shopsmart.promotions", "msg": message, "args": (), **extra}
            )
        )

    monkeypatch.setattr("src.services.cart_service._promotion_logger.info", capture_promotion_log)
    user_id = uuid4()
    product = await _product(test_db)
    now = datetime.now(timezone.utc)
    promotion = Promotion(
        code="SAVE20",
        name="Coupon offer",
        promotion_type="percentage",
        value=20,
        starts_at=now - timedelta(days=1),
        ends_at=now + timedelta(days=1),
        active=True,
        scope_type="all",
    )
    test_db.add(promotion)
    await test_db.flush()
    service = CartService(test_db)
    await service.add_item(user_id, product.id, 1)

    applied = await service.apply_coupon(user_id, " save20 ")

    assert applied["coupon_code"] == "SAVE20"
    assert applied["coupon_evaluation"]["eligible"] is True
    assert applied["total_cents"] == 1039

    with pytest.raises(AppException) as error:
        await service.apply_coupon(user_id, "NOTREAL")

    assert error.value.status_code == 422
    current = await service.get_cart(user_id)
    assert current["coupon_code"] == "SAVE20"
    checked = await service.check_coupon(user_id, "NOTREAL")
    assert checked["coupon_evaluation"]["eligible"] is False
    assert checked["items"][0]["product_id"] == product.id
    assert [record.operation for record in promotion_logs] == [
        "coupon_apply",
        "coupon_apply",
        "coupon_check",
    ]
    assert all(record.duration_ms >= 0 for record in promotion_logs)
    assert all(len(record.coupon_hash) == 64 for record in promotion_logs)
    assert [record.status_code for record in promotion_logs] == [200, 422, 200]
    assert promotion_logs[0].promotion_id == str(promotion.id)
    assert promotion_logs[0].eligible is True
    assert promotion_logs[0].discount_cents == 260
    assert promotion_logs[2].success is True
    assert promotion_logs[2].eligible is False
    formatted_logs = [JsonLogFormatter().format(record) for record in promotion_logs]
    assert all("SAVE20" not in message and "NOTREAL" not in message for message in formatted_logs)
    assert all(user_id.hex not in message for message in formatted_logs)
