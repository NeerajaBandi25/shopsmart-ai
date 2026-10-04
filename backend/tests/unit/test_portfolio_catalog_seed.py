from collections import Counter
from importlib import import_module
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import (
    CheckConstraint,
    Column,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    func,
    insert,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.product import Product
from src.schemas.product import ProductResponse
from src.seed.portfolio_catalog import (
    CATALOG_CATEGORIES,
    CATALOG_DATABASE,
    CATALOG_OPT_IN,
    CATALOG_SIZE,
    CatalogSeedCollisionError,
    CatalogSeedSafetyError,
    build_catalog_products,
    repair_catalog_products,
    seed_catalog_products,
    validate_catalog_target,
)

category_migration = import_module("migrations.versions.015_portfolio_catalog_categories")
portfolio_family_migration = import_module(
    "migrations.versions.016_portfolio_product_families"
)


def _local_environment() -> dict[str, str]:
    return {"SHOPSMART_ENV": "test", CATALOG_OPT_IN: "true"}


def test_catalog_fixture_is_stable_descriptive_and_uses_verified_product_photography():
    first = build_catalog_products()
    second = build_catalog_products()

    assert len(first) == CATALOG_SIZE == 1200
    assert [(product.id, product.sku, product.name) for product in first] == [
        (product.id, product.sku, product.name) for product in second
    ]
    assert len({product.sku for product in first}) == CATALOG_SIZE
    assert len({product.name for product in first}) == CATALOG_SIZE
    assert {product.category for product in first} == set(CATALOG_CATEGORIES)
    assert Counter(product.category for product in first) == {
        category: 80 for category in CATALOG_CATEGORIES
    }
    assert all("Model " not in product.name for product in first)
    assert all("Fictional catalog sample" not in product.description for product in first)
    image_urls = {product.image_url for product in first}
    assert len(image_urls) == 77
    assert all(
        product.image_url and product.image_url.startswith("/images/products/portfolio/")
        for product in first
    )
    assert all(product.image_alt for product in first)
    assert all("OpenAI built-in image_gen" in product.image_creator for product in first)
    assert all(
        product.image_license == "Repository-created AI-generated portfolio-family image"
        for product in first
    )
    assert all(len(product.image_sha256 or "") == 64 for product in first)
    assert all(product.specifications for product in first)
    assert all(
        {"Subcategory", "Variant", "Key details"}
        <= product.specifications.keys()
        for product in first
    )
    assert all("Rating" not in product.specifications for product in first)
    assert all("Review count" not in product.specifications for product in first)
    assert all(0 <= product.price < 100_000_000 for product in first)
    assert all(product.stock_quantity >= 0 for product in first)
    assert any(product.stock_quantity == 0 for product in first)
    assert any(product.stock_quantity > 0 for product in first)
    assert all(
        product.list_price is None or product.list_price >= product.price for product in first
    )


def test_shortlisted_laptop_families_expose_hero_and_alternate_image_roles():
    products = {product.sku: product for product in build_catalog_products()}
    expected = {
        "PORT-LAPTOPS-01-03": "vellune-studybook",
        "PORT-LAPTOPS-05-06": "vellune-copperfield",
        "PORT-LAPTOPS-06-05": "merroway-featherweight",
    }

    for sku, family in expected.items():
        product = products[sku]
        gallery = ProductResponse.model_validate(product).image_gallery
        assert [image["role"] for image in gallery] == ["hero", "alternate"]
        assert gallery[0]["url"].endswith(f"{family}-hero.png")
        assert gallery[1]["url"].endswith(f"{family}-alt.png")

    for family_index in ("01", "05", "06"):
        family_urls = {
            product.image_url
            for product in products.values()
            if product.sku.startswith(f"PORT-LAPTOPS-{family_index}-")
        }
        assert len(family_urls) == 1


def test_category_migration_preserves_rows_and_allows_new_families():
    engine = create_engine("sqlite:///:memory:")
    metadata = MetaData()
    legacy_categories = (
        "'laptops', 'phones', 'accessories', 'footwear', 'fashion', 'appliances', "
        "'home', 'beauty', 'groceries'"
    )
    products = Table(
        "products",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("category", String(32), nullable=True),
        CheckConstraint(
            f"category IS NULL OR category IN ({legacy_categories})",
            name="ck_products_category_canonical",
        ),
    )
    try:
        metadata.create_all(engine)
        with engine.begin() as connection:
            connection.execute(insert(products).values(id=1, category="laptops"))
            with Operations.context(MigrationContext.configure(connection)):
                category_migration.upgrade()
                portfolio_family_migration.upgrade()

            assert connection.execute(select(products.c.category)).scalar_one() == "laptops"
            connection.execute(
                insert(products),
                [
                    {"id": index + 2, "category": category}
                    for index, category in enumerate(CATALOG_CATEGORIES)
                ],
            )
            assert (
                connection.execute(select(func.count()).select_from(products)).scalar_one()
                == len(CATALOG_CATEGORIES) + 1
            )
    finally:
        engine.dispose()


def test_catalog_seed_requires_exact_database_opt_in_and_loopback():
    local_url = f"postgresql+asyncpg://local:local@127.0.0.1/{CATALOG_DATABASE}"
    validate_catalog_target(True, _local_environment(), local_url)

    with pytest.raises(CatalogSeedSafetyError):
        validate_catalog_target(False, _local_environment(), local_url)
    with pytest.raises(CatalogSeedSafetyError):
        validate_catalog_target(
            True,
            _local_environment(),
            "postgresql+asyncpg://local:local@localhost/shopsmart_ai",
        )
    with pytest.raises(CatalogSeedSafetyError):
        validate_catalog_target(
            True,
            _local_environment(),
            f"postgresql+asyncpg://local:local@remote.example/{CATALOG_DATABASE}",
        )
    with pytest.raises(CatalogSeedSafetyError):
        validate_catalog_target(
            True,
            _local_environment(),
            f"postgresql+asyncpg://local:local@localhost/{CATALOG_DATABASE}?host=remote.example",
        )
    with pytest.raises(CatalogSeedSafetyError):
        validate_catalog_target(
            True,
            {**_local_environment(), "APP_ENV": "production"},
            local_url,
        )


async def test_seed_is_additive_idempotent_and_preserves_existing_products(test_db: AsyncSession):
    unrelated = Product(
        id=uuid4(),
        name="Developer-owned product",
        description="Keep this row.",
        sku="KEEP-CATALOG-001",
        price=1234,
        stock_quantity=7,
        max_purchase_quantity=2,
        is_active=True,
    )
    test_db.add(unrelated)
    await test_db.flush()

    first = await seed_catalog_products(test_db)
    seeded_sku = build_catalog_products()[0].sku
    seeded = await test_db.scalar(select(Product).where(Product.sku == seeded_sku))
    seeded.stock_quantity = 0
    await test_db.flush()
    second = await seed_catalog_products(test_db)

    assert first == {"inserted": CATALOG_SIZE, "already_present": 0}
    assert second == {"inserted": 0, "already_present": CATALOG_SIZE}
    assert seeded.stock_quantity == 0
    assert await test_db.get(Product, unrelated.id) is unrelated
    assert await test_db.scalar(select(func.count()).select_from(Product)) == CATALOG_SIZE + 1


async def test_seed_refuses_reserved_sku_owned_by_another_product(test_db: AsyncSession):
    conflict = Product(
        id=uuid4(),
        name="Not the reserved fixture",
        description=None,
        sku=build_catalog_products()[0].sku,
        price=1000,
        stock_quantity=1,
        max_purchase_quantity=1,
        is_active=True,
    )
    test_db.add(conflict)
    await test_db.flush()

    with pytest.raises(CatalogSeedCollisionError):
        await seed_catalog_products(test_db)

    assert await test_db.get(Product, conflict.id) is conflict
    assert await test_db.scalar(select(func.count()).select_from(Product)) == 1


async def test_repair_refreshes_art_alignment_without_resetting_live_stock(test_db: AsyncSession):
    await seed_catalog_products(test_db)
    expected = next(p for p in build_catalog_products() if p.category == "accessories")
    row = await test_db.get(Product, expected.id)
    row.name = "Braided USB-C cable"
    row.stock_quantity = 0
    await test_db.flush()
    assert await repair_catalog_products(test_db) == {"updated": 1200}
    assert row.name == expected.name
    assert "Sunglasses" in row.name
    assert row.image_url.endswith("accessories/01.jpg")
    assert row.stock_quantity == 0
    assert await test_db.scalar(select(func.count()).select_from(Product)) == 1200


async def test_repair_refuses_reserved_identity_collision(test_db: AsyncSession):
    conflict = Product(id=uuid4(), name="Owned by someone else", sku=build_catalog_products()[0].sku,
                       price=100, stock_quantity=1, max_purchase_quantity=1, is_active=True)
    test_db.add(conflict)
    await test_db.flush()
    with pytest.raises(CatalogSeedCollisionError):
        await repair_catalog_products(test_db)
    assert conflict.name == "Owned by someone else"


def test_authored_archetypes_match_distinct_photo_families_and_memory_is_explicit():
    products = build_catalog_products()
    for category, expected in {"accessories": ("Sunglasses", "Backpack", "Wallet", "Belt", "Cap"),
                               "kitchen_appliances": ("Toaster", "Blender", "Kettle", "Coffee", "Mixer"),
                               "home_living": ("Lamp", "Sofa", "Plant", "Clock", "Shelf")}.items():
        for number, name in enumerate(expected, 1):
            related = [p for p in products if p.category == category and p.image_url.endswith(f"/{number:02d}.jpg")]
            assert related and all(name in p.name for p in related)
    assert all("RAM" in p.specifications and "Graphics" in p.specifications for p in products if p.category == "laptops")


def test_public_presentation_is_record_driven_and_ignores_malformed_metadata():
    product = build_catalog_products()[80]
    response = ProductResponse.model_validate(product).model_dump(mode="json")
    assert response["delivery"] == "Standard portfolio delivery; timing confirmed at checkout"
    assert response["highlights"][0] == product.specifications["Key details"]
    assert response["image_gallery"] == [{"url": product.image_url, "alt": product.image_alt}]
    product.specifications = {"_presentation": "malformed legacy metadata"}
    legacy = ProductResponse.model_validate(product).model_dump(mode="json")
    assert legacy["delivery"] is None
    assert legacy["highlights"] == legacy["image_gallery"] == []
