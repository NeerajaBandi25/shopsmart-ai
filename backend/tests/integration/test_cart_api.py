"""Focused authenticated cart API tests using the in-memory test database."""

from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy import select

from src.api.v1.cart_routes import router as cart_router
from src.core.security import hash_password
from src.main import app
from src.models.cart import Cart, CartItem
from src.models.product import Product
from src.repositories.user_repository import UserRepository

app.include_router(cart_router, prefix="/api/v1")


async def _login(client: AsyncClient, email: str, password: str = "Secure123!") -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    csrf_response = await client.get("/api/v1/auth/csrf")
    assert csrf_response.status_code == 200
    return csrf_response.json()["csrf_token"]


async def _create_product(test_db, *, active: bool = True) -> Product:
    product = Product(
        name="Desk Lamp",
        description=None,
        sku=f"CART-LAMP-{uuid4().hex[:8]}",
        price=1299,
        stock_quantity=8,
        max_purchase_quantity=3,
        is_active=active,
    )
    test_db.add(product)
    await test_db.flush()
    return product


class TestAuthenticatedCartApi:
    async def test_anonymous_cart_requests_are_denied(self, test_client: AsyncClient):
        response = await test_client.get("/api/v1/cart")

        assert response.status_code == 401

    async def test_mutations_require_csrf(self, test_client: AsyncClient, test_db):
        product = await _create_product(test_db)
        await UserRepository(test_db).create_user(
            "cart-user@example.com", hash_password("Secure123!")
        )
        await test_db.commit()
        await _login(test_client, "cart-user@example.com")

        response = await test_client.post(
            "/api/v1/cart/items", json={"product_id": str(product.id), "quantity": 1}
        )

        assert response.status_code == 403

    async def test_add_increment_set_and_delete_use_csrf_and_server_prices(
        self, test_client: AsyncClient, test_db
    ):
        product = await _create_product(test_db)
        await UserRepository(test_db).create_user(
            "cart-user@example.com", hash_password("Secure123!")
        )
        await test_db.commit()
        csrf_token = await _login(test_client, "cart-user@example.com")
        headers = {"X-CSRF-Token": csrf_token}

        added = await test_client.post(
            "/api/v1/cart/items",
            json={"product_id": str(product.id), "quantity": 1},
            headers=headers,
        )
        incremented = await test_client.post(
            "/api/v1/cart/items",
            json={"product_id": str(product.id), "quantity": 1},
            headers=headers,
        )
        updated = await test_client.put(
            f"/api/v1/cart/items/{product.id}",
            json={"quantity": 3},
            headers=headers,
        )
        deleted = await test_client.delete(f"/api/v1/cart/items/{product.id}", headers=headers)

        assert added.status_code == 200
        assert incremented.json()["items"][0]["quantity"] == 2
        assert updated.json()["items"][0]["unit_price"] == 1299
        assert updated.json()["items"][0]["line_total"] == 3897
        assert updated.json()["subtotal"] == 3897
        assert deleted.json() == {"items": [], "subtotal": 0, "currency": "USD"}

    async def test_invalid_or_missing_csrf_is_rejected(self, test_client: AsyncClient, test_db):
        product = await _create_product(test_db)
        await UserRepository(test_db).create_user(
            "cart-user@example.com", hash_password("Secure123!")
        )
        await test_db.commit()
        await _login(test_client, "cart-user@example.com")

        response = await test_client.post(
            "/api/v1/cart/items",
            json={"product_id": str(product.id), "quantity": 1},
            headers={"X-CSRF-Token": "invalid-token"},
        )

        assert response.status_code == 403

    async def test_rejects_inactive_missing_and_over_limit_products(
        self, test_client: AsyncClient, test_db
    ):
        product = await _create_product(test_db)
        inactive = await _create_product(test_db, active=False)
        await UserRepository(test_db).create_user(
            "cart-user@example.com", hash_password("Secure123!")
        )
        await test_db.commit()
        headers = {"X-CSRF-Token": await _login(test_client, "cart-user@example.com")}

        over_limit = await test_client.post(
            "/api/v1/cart/items",
            json={"product_id": str(product.id), "quantity": 4},
            headers=headers,
        )
        inactive_response = await test_client.post(
            "/api/v1/cart/items",
            json={"product_id": str(inactive.id), "quantity": 1},
            headers=headers,
        )

        assert over_limit.status_code == 400
        assert inactive_response.status_code == 404

    async def test_cart_is_private_and_empty_cart_has_zero_total(
        self, test_client: AsyncClient, test_db, test_user_data_in_db
    ):
        product = await _create_product(test_db)
        csrf_token = await _login(
            test_client,
            test_user_data_in_db["email"],
            test_user_data_in_db["password"],
        )
        await test_client.post(
            "/api/v1/cart/items",
            json={"product_id": str(product.id), "quantity": 2},
            headers={"X-CSRF-Token": csrf_token},
        )

        second_client = AsyncClient(app=app, base_url="https://test")
        try:
            await UserRepository(test_db).create_user(
                "other-cart-user@example.com", hash_password("Secure123!")
            )
            await test_db.commit()
            await _login(second_client, "other-cart-user@example.com")
            response = await second_client.get("/api/v1/cart")
        finally:
            await second_client.aclose()

        assert response.status_code == 200
        assert response.json() == {"items": [], "subtotal": 0, "currency": "USD"}

    async def test_zero_quantity_is_rejected_by_request_validation(
        self, test_client: AsyncClient, test_db, test_user_data_in_db
    ):
        product = await _create_product(test_db)
        headers = {
            "X-CSRF-Token": await _login(
                test_client,
                test_user_data_in_db["email"],
                test_user_data_in_db["password"],
            )
        }

        response = await test_client.post(
            "/api/v1/cart/items",
            json={"product_id": str(product.id), "quantity": 0},
            headers=headers,
        )

        assert response.status_code == 422

    async def test_empty_cart_does_not_create_database_rows(
        self, test_client: AsyncClient, test_db, test_user_data_in_db
    ):
        await _login(
            test_client,
            test_user_data_in_db["email"],
            test_user_data_in_db["password"],
        )

        response = await test_client.get("/api/v1/cart")
        carts = (await test_db.execute(select(Cart))).scalars().all()
        items = (await test_db.execute(select(CartItem))).scalars().all()

        assert response.json() == {"items": [], "subtotal": 0, "currency": "USD"}
        assert carts == []
        assert items == []
