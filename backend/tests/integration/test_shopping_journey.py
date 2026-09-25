"""Prove a seeded catalog-to-order journey through the public API."""

from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from scripts.seed_demo_products import seed_missing_products
from src.models.product import Product


@pytest.mark.asyncio
async def test_shopper_browses_updates_cart_checks_out_and_views_order(
    test_client: AsyncClient, test_db: AsyncSession
):
    await seed_missing_products(test_db)
    await test_db.commit()

    email = "journey@example.com"
    password = "Journey123!"
    registration = await test_client.post(
        "/api/v1/auth/register", json={"email": email, "password": password}
    )
    assert registration.status_code == 201

    login = await test_client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert login.status_code == 200
    cookies = login.cookies
    csrf_response = await test_client.get("/api/v1/auth/csrf", cookies=cookies)
    assert csrf_response.status_code == 200
    csrf_headers = {"X-CSRF-Token": csrf_response.json()["csrf_token"]}

    catalog = await test_client.get("/api/v1/products?limit=8")
    assert catalog.status_code == 200
    assert len(catalog.json()["items"]) == 8
    first_product = catalog.json()["items"][0]
    second_product = catalog.json()["items"][1]

    added = await test_client.post(
        "/api/v1/cart/items",
        json={"product_id": first_product["id"], "quantity": 1},
        cookies=cookies,
        headers=csrf_headers,
    )
    assert added.status_code == 200
    incremented = await test_client.post(
        "/api/v1/cart/items",
        json={"product_id": first_product["id"], "quantity": 1},
        cookies=cookies,
        headers=csrf_headers,
    )
    assert incremented.status_code == 200
    updated = await test_client.put(
        f"/api/v1/cart/items/{first_product['id']}",
        json={"quantity": 3},
        cookies=cookies,
        headers=csrf_headers,
    )
    assert updated.status_code == 200
    await test_client.post(
        "/api/v1/cart/items",
        json={"product_id": second_product["id"], "quantity": 1},
        cookies=cookies,
        headers=csrf_headers,
    )
    removed = await test_client.delete(
        f"/api/v1/cart/items/{second_product['id']}",
        cookies=cookies,
        headers=csrf_headers,
    )
    assert removed.status_code == 200
    cart_before_checkout = await test_client.get("/api/v1/cart", cookies=cookies)
    assert cart_before_checkout.status_code == 200
    assert len(cart_before_checkout.json()["items"]) == 1
    assert cart_before_checkout.json()["items"][0]["quantity"] == 3

    product_before = await test_db.scalar(
        select(Product).where(Product.id == UUID(first_product["id"]))
    )
    stock_before = product_before.stock_quantity
    payload = {"items": [{"product_id": first_product["id"], "quantity": 3}]}
    checkout_headers = {**csrf_headers, "Idempotency-Key": "journey-order-1"}
    order_response = await test_client.post(
        "/api/v1/orders/checkout",
        json=payload,
        cookies=cookies,
        headers=checkout_headers,
    )
    assert order_response.status_code == 201
    order = order_response.json()
    assert order["total_cents"] == first_product["price"] * 3
    assert order["items"][0]["product_sku"] == first_product["sku"]

    replay = await test_client.post(
        "/api/v1/orders/checkout",
        json=payload,
        cookies=cookies,
        headers=checkout_headers,
    )
    assert replay.status_code == 201
    assert replay.json()["id"] == order["id"]
    await test_db.refresh(product_before)
    assert product_before.stock_quantity == stock_before - 3

    history = await test_client.get("/api/v1/orders", cookies=cookies)
    assert history.status_code == 200
    assert [entry["id"] for entry in history.json()] == [order["id"]]

    cart_cleared = await test_client.delete(
        f"/api/v1/cart/items/{first_product['id']}",
        cookies=cookies,
        headers=csrf_headers,
    )
    assert cart_cleared.status_code == 200
    assert cart_cleared.json()["items"] == []