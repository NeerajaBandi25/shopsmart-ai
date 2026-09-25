import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from scripts.seed_demo_products import DEMO_PRODUCTS, main, run_seed
from src.models.product import Product


@pytest.fixture(autouse=True)
def deduplicate_product_indexes_for_sqlite(monkeypatch):
    indexes = {index.name: index for index in Product.__table__.indexes}
    monkeypatch.setattr(Product.__table__, "indexes", set(indexes.values()))


@pytest.fixture
def session_factory(test_engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(test_engine, expire_on_commit=False)


async def _product_count(session_factory: async_sessionmaker[AsyncSession]) -> int:
    async with session_factory() as session:
        result = await session.execute(select(func.count()).select_from(Product))
        return result.scalar_one()


@pytest.mark.parametrize(
    ("apply", "allow_demo_seeding"),
    [(False, None), (True, None), (False, "true")],
)
async def test_refuses_without_both_opt_ins(
    session_factory: async_sessionmaker[AsyncSession],
    apply: bool,
    allow_demo_seeding: str | None,
):
    exit_code = await run_seed(
        apply,
        allow_demo_seeding,
        session_factory=session_factory,
    )

    assert exit_code == 2
    assert await _product_count(session_factory) == 0


def test_cli_refuses_by_default(monkeypatch, capsys):
    monkeypatch.delenv("SHOPSMART_ALLOW_DEMO_SEEDING", raising=False)

    assert main([]) == 2
    assert "Demo seeding refused; no changes made." in capsys.readouterr().out


async def test_explicit_opt_in_inserts_fictional_products(
    session_factory: async_sessionmaker[AsyncSession],
):
    exit_code = await run_seed(True, "true", session_factory=session_factory)

    assert exit_code == 0
    assert await _product_count(session_factory) == len(DEMO_PRODUCTS) >= 8
    async with session_factory() as session:
        products = (await session.execute(select(Product))).scalars().all()

    assert {product.sku for product in products} == {
        product.sku for product in DEMO_PRODUCTS
    }
    assert all(isinstance(product.price, int) and product.price > 0 for product in products)
    assert all(product.stock_quantity > 0 for product in products)


async def test_rerun_does_not_duplicate_or_reset_seeded_products(
    session_factory: async_sessionmaker[AsyncSession],
):
    first_exit_code = await run_seed(True, "true", session_factory=session_factory)
    second_exit_code = await run_seed(True, "true", session_factory=session_factory)

    assert first_exit_code == second_exit_code == 0
    assert await _product_count(session_factory) == len(DEMO_PRODUCTS)


async def test_preserves_existing_record_with_a_seed_sku(
    session_factory: async_sessionmaker[AsyncSession],
):
    seeded = DEMO_PRODUCTS[0]
    async with session_factory() as session:
        existing = Product(
            name="Locally customized product",
            description="Keep this local description.",
            sku=seeded.sku,
            price=12345,
            stock_quantity=7,
            max_purchase_quantity=2,
            is_active=False,
        )
        session.add(existing)
        await session.commit()
        existing_id = existing.id

    exit_code = await run_seed(True, "true", session_factory=session_factory)

    assert exit_code == 0
    async with session_factory() as session:
        products = (await session.execute(select(Product))).scalars().all()
        preserved = await session.get(Product, existing_id)

    assert len(products) == len(DEMO_PRODUCTS)
    assert preserved is not None
    assert preserved.name == "Locally customized product"
    assert preserved.description == "Keep this local description."
    assert preserved.price == 12345
    assert preserved.stock_quantity == 7
    assert preserved.max_purchase_quantity == 2
    assert preserved.is_active is False
