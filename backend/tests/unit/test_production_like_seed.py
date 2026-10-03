from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.core.security import verify_password
from src.models.ai import KnowledgeSource
from src.models.cart import Cart, CartItem
from src.models.order import Order, OrderItem
from src.models.product import Product
from src.models.promotion import Promotion
from src.models.user import User
from src.seed.production_like import (
    DATASET_VERSION,
    SeedOwnershipConflict,
    SeedSafetyError,
    build_products,
    load_manifest,
    reset_seeded_data,
    seed_dataset,
    stable_id,
    user_id,
    validate_target,
)


@pytest.fixture
def session_factory(test_engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(test_engine, expire_on_commit=False)


def _local_environment() -> dict[str, str]:
    return {
        "SHOPSMART_ENV": "test",
        "SHOPSMART_ALLOW_DEMO_SEEDING": "true",
        "SHOPSMART_LOCAL_SEED_PASSWORD": "LocalOnly!2026",
    }


def test_dataset_is_deterministic_realistic_and_uses_only_supported_product_fields():
    manifest = load_manifest()
    first = build_products(manifest)
    second = build_products(manifest)

    assert manifest["version"] == DATASET_VERSION
    assert len(first) == len(second) == 1000
    assert [(item.id, item.sku, item.price, item.stock_quantity) for item in first] == [
        (item.id, item.sku, item.price, item.stock_quantity) for item in second
    ]
    assert len({item.sku for item in first}) == 1000
    assert all(
        item.category in {category["key"] for category in manifest["categories"]} for item in first
    )
    assert all(not hasattr(item, "variants") for item in first)
    assert any(item.is_active and item.stock_quantity == 0 for item in first)
    assert any(item.is_active and 0 < item.stock_quantity <= 3 for item in first)
    assert any(item.is_active and item.stock_quantity > 3 for item in first)
    assert min(item.price for item in first) < 5000 < max(item.price for item in first)


def test_seed_requires_explicit_local_opt_in_and_loopback_database():
    local = _local_environment()
    local_url = "postgresql+asyncpg://test:test@localhost/shopsmart_test"
    validate_target("seed", True, None, local, local_url)
    validate_target("seed", True, None, local, "postgresql+asyncpg:///shopsmart_test")

    with pytest.raises(SeedSafetyError):
        validate_target("seed", False, None, local, local_url)
    with pytest.raises(SeedSafetyError):
        validate_target("seed", True, None, {**local, "APP_ENV": "production"}, local_url)
    with pytest.raises(SeedSafetyError):
        validate_target(
            "seed", True, None, local, "postgresql+asyncpg://test:test@db.example/shopsmart"
        )
    with pytest.raises(SeedSafetyError):
        validate_target(
            "seed",
            True,
            None,
            {**local, "PGHOST": "database.example"},
            "postgresql+asyncpg:///shopsmart_test",
        )
    with pytest.raises(SeedSafetyError):
        validate_target("reset-seeded-data", True, None, local, local_url)


async def test_seed_is_repeatable_and_reset_preserves_unrelated_rows(session_factory):
    manifest = load_manifest()
    async with session_factory() as session:
        unrelated_user = User(
            id=uuid4(), email="developer@example.invalid", password_hash="not-a-login-hash"
        )
        unrelated_product = Product(
            id=uuid4(),
            name="Developer-owned product",
            description=None,
            sku="DEVELOPER-KEEP-001",
            price=1234,
            stock_quantity=2,
            max_purchase_quantity=2,
            is_active=True,
        )
        session.add_all([unrelated_user, unrelated_product])
        await session.flush()
        unrelated_cart = Cart(id=uuid4(), user_id=unrelated_user.id)
        session.add(unrelated_cart)
        await session.flush()
        session.add(
            CartItem(
                id=uuid4(),
                cart_id=unrelated_cart.id,
                product_id=unrelated_product.id,
                quantity=1,
            )
        )
        await session.commit()

        first = await seed_dataset(session, "LocalOnly!2026")
        second = await seed_dataset(session, "LocalOnly!2026")
        assert first == second
        assert first["products"] == 1000
        assert first["users"] == 7
        assert first["promotions"] == len(manifest["promotions"])
        assert await session.scalar(select(func.count()).select_from(Promotion)) == len(
            manifest["promotions"]
        )
        assert first["knowledge_sources"] == len(manifest["knowledge"])

        seeded_user = await session.get(User, user_id("returning-customer"))
        assert seeded_user is not None
        assert verify_password("LocalOnly!2026", seeded_user.password_hash)
        assert await session.scalar(select(func.count()).select_from(Product)) == 1001
        assert await session.scalar(select(func.count()).select_from(Order)) == first["orders"] + 0
        assert await session.scalar(select(func.count()).select_from(KnowledgeSource)) == len(
            manifest["knowledge"]
        )

        await reset_seeded_data(session)

        assert await session.get(User, user_id("returning-customer")) is None
        assert await session.scalar(select(func.count()).select_from(Product)) == 1
        assert await session.scalar(select(func.count()).select_from(User)) == 1
        assert await session.scalar(select(func.count()).select_from(Cart)) == 1
        assert await session.scalar(select(func.count()).select_from(CartItem)) == 1
        assert await session.scalar(select(func.count()).select_from(Order)) == 0
        assert await session.scalar(select(func.count()).select_from(Promotion)) == 0
        assert await session.scalar(select(func.count()).select_from(KnowledgeSource)) == 0
        assert await session.get(Product, unrelated_product.id) is not None


async def test_reset_refuses_if_an_unseeded_shopper_references_seeded_product(session_factory):
    async with session_factory() as session:
        await seed_dataset(session, "LocalOnly!2026")
        external_user = User(
            id=uuid4(), email="external@example.invalid", password_hash="not-a-login-hash"
        )
        external_product = await session.scalar(
            select(Product).where(Product.sku == "SYNTH-EVAL-V1-00003")
        )
        session.add(external_user)
        await session.flush()
        cart = Cart(id=uuid4(), user_id=external_user.id)
        session.add(cart)
        await session.flush()
        session.add(
            CartItem(id=uuid4(), cart_id=cart.id, product_id=external_product.id, quantity=1)
        )
        await session.commit()

        with pytest.raises(SeedOwnershipConflict):
            await reset_seeded_data(session)

        assert await session.get(Product, external_product.id) is not None
        assert await session.get(User, external_user.id) is not None


async def test_reset_refuses_reserved_cart_id_owned_by_unrelated_user(session_factory):
    async with session_factory() as session:
        await seed_dataset(session, "LocalOnly!2026")
        external_user = User(
            id=uuid4(), email="cart-collision@example.invalid", password_hash="not-a-login-hash"
        )
        external_product = Product(
            id=uuid4(),
            name="Unrelated product",
            description=None,
            sku="UNRELATED-CART-PRODUCT",
            price=1234,
            stock_quantity=2,
            max_purchase_quantity=2,
            is_active=True,
        )
        session.add_all([external_user, external_product])
        await session.flush()
        reserved_cart_id = stable_id("cart", "new-customer")
        cart = await session.get(Cart, reserved_cart_id)
        cart.user_id = external_user.id
        item = CartItem(
            id=uuid4(), cart_id=reserved_cart_id, product_id=external_product.id, quantity=1
        )
        session.add(item)
        await session.commit()

        with pytest.raises(SeedOwnershipConflict):
            await reset_seeded_data(session)

        assert (await session.get(Cart, reserved_cart_id)).user_id == external_user.id
        assert await session.get(CartItem, item.id) is not None
        assert await session.get(Product, external_product.id) is not None
        assert await session.get(User, external_user.id) is not None


async def test_reset_refuses_unmarked_order_from_a_reserved_account(session_factory):
    async with session_factory() as session:
        await seed_dataset(session, "LocalOnly!2026")
        seeded_user = await session.get(User, user_id("returning-customer"))
        product = await session.scalar(select(Product).where(Product.sku == "SYNTH-EVAL-V1-00003"))
        session.add(
            Order(
                id=uuid4(),
                user_id=seeded_user.id,
                idempotency_key="developer-order-not-owned-by-seed",
                request_hash="a" * 64,
                status="placed",
                subtotal_cents=product.price,
                discount_total_cents=0,
                total_cents=product.price,
                promotion_snapshot=[],
                items=[
                    OrderItem(
                        id=uuid4(),
                        product_id=product.id,
                        product_name=product.name,
                        product_sku=product.sku,
                        unit_price_cents=product.price,
                        quantity=1,
                        line_total_cents=product.price,
                    )
                ],
            )
        )
        await session.commit()

        with pytest.raises(SeedOwnershipConflict):
            await reset_seeded_data(session)

        assert await session.get(User, seeded_user.id) is not None
        assert (
            await session.scalar(
                select(Order).where(Order.idempotency_key == "developer-order-not-owned-by-seed")
            )
            is not None
        )


async def test_reserved_product_identity_collision_is_not_claimed(session_factory):
    async with session_factory() as session:
        session.add(
            Product(
                id=uuid4(),
                name="Existing developer product",
                description=None,
                sku="SYNTH-EVAL-V1-00001",
                price=777,
                stock_quantity=1,
                max_purchase_quantity=1,
                is_active=True,
            )
        )
        await session.commit()

        with pytest.raises(SeedOwnershipConflict):
            await seed_dataset(session, "LocalOnly!2026")

        existing = await session.scalar(select(Product).where(Product.sku == "SYNTH-EVAL-V1-00001"))
        assert existing.name == "Existing developer product"
        assert stable_id("product", "SYNTH-EVAL-V1-00001") != existing.id


async def test_reset_refuses_to_delete_product_referenced_by_unrelated_promotion(
    session_factory,
):
    from datetime import datetime, timedelta, timezone

    async with session_factory() as session:
        await seed_dataset(session, "LocalOnly!2026")
        seeded_product = await session.scalar(
            select(Product).where(Product.sku == "SYNTH-EVAL-V1-00003")
        )
        external_promotion = Promotion(
            id=uuid4(),
            code="EXTERNAL-KEEP",
            name="Developer offer",
            promotion_type="fixed",
            value=100,
            starts_at=datetime.now(timezone.utc) - timedelta(days=1),
            ends_at=datetime.now(timezone.utc) + timedelta(days=1),
            active=True,
            scope_type="product",
            scope_product_id=seeded_product.id,
        )
        session.add(external_promotion)
        await session.commit()

        with pytest.raises(SeedOwnershipConflict):
            await reset_seeded_data(session)

        assert await session.get(Promotion, external_promotion.id) is not None
        assert await session.get(Product, seeded_product.id) is not None
        assert await session.get(User, user_id("returning-customer")) is not None
