"""Focused tests for cart persistence and business rules."""

from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import ValidationError
from src.models.cart import Cart, CartItem
from src.models.product import Product
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

    assert cart == {"items": [], "subtotal": 0, "currency": "USD"}


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
            "unit_price": 1299,
            "quantity": 3,
            "line_total": 3897,
            "stock_quantity": 8,
            "max_purchase_quantity": 3,
        }
    ]
    assert cart["subtotal"] == 3897
    assert cart["currency"] == "USD"


async def test_set_quantity_is_exact_and_remove_clears_line(test_db: AsyncSession):
    user_id = uuid4()
    product = await _product(test_db)
    service = CartService(test_db)

    await service.add_item(user_id, product.id, 2)
    updated = await service.set_item_quantity(user_id, product.id, 1)
    removed = await service.remove_item(user_id, product.id)

    assert updated["items"][0]["quantity"] == 1
    assert updated["subtotal"] == 1299
    assert removed == {"items": [], "subtotal": 0, "currency": "USD"}


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
