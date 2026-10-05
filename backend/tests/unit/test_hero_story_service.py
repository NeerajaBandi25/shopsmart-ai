"""The guided homepage story must stay grounded in purchasable catalog rows."""

import pytest

from src.models.product import Product
from src.services.hero_story_service import HeroStoryService


@pytest.mark.asyncio
async def test_hero_story_uses_distinct_in_stock_under_budget_products(test_db):
    products = [
        Product(
            name="Study 8",
            sku="HERO-8",
            category="laptops",
            price=4_800_000,
            stock_quantity=8,
            image_url="/study.jpg",
            specifications={"RAM": "8 GB RAM", "Storage": "256 GB SSD"},
        ),
        Product(
            name="Study 16",
            sku="HERO-16",
            category="laptops",
            price=5_500_000,
            stock_quantity=4,
            image_url="/study.jpg",
            specifications={
                "RAM": "16 GB RAM",
                "Processor": "8-core processor",
                "Storage": "512 GB SSD",
            },
        ),
        Product(
            name="Office 16 / 512 GB",
            sku="HERO-OFFICE-512",
            category="laptops",
            price=5_800_000,
            stock_quantity=3,
            image_url="/office.jpg",
            specifications={"RAM": "16 GB RAM", "Storage": "512 GB SSD"},
        ),
        Product(
            name="Office 16",
            sku="HERO-OFFICE",
            category="laptops",
            price=5_900_000,
            stock_quantity=3,
            image_url="/office.jpg",
            specifications={
                "RAM": "16 GB RAM",
                "Processor": "8-core processor",
                "Storage": "1 TB SSD",
            },
        ),
        Product(
            name="Travel 16",
            sku="HERO-TRAVEL",
            category="laptops",
            price=6_200_000,
            stock_quantity=2,
            image_url="/travel.jpg",
            specifications={"RAM": "16 GB RAM", "Graphics": "Integrated graphics"},
        ),
        Product(
            name="Over budget",
            sku="HERO-OVER",
            category="laptops",
            price=7_100_000,
            stock_quantity=2,
            image_url="/over.jpg",
            specifications={"RAM": "32 GB RAM"},
        ),
        Product(
            name="No stock",
            sku="HERO-EMPTY",
            category="laptops",
            price=4_000_000,
            stock_quantity=0,
            image_url="/empty.jpg",
            specifications={"RAM": "32 GB RAM"},
        ),
    ]
    test_db.add_all(products)
    await test_db.flush()

    story = await HeroStoryService(test_db).get_story()

    assert story is not None
    assert "coding" in story.query.lower()
    assert "react" not in story.query.lower()
    assert [product.name for product in story.candidates] == [
        "Study 16",
        "Office 16",
        "Travel 16",
    ]
    assert len({product.image_url for product in story.candidates}) == 3
    assert story.candidates[1].specifications["Storage"] == "1 TB SSD"
    assert story.recommended_product_id == products[1].id
    assert story.savings_minor == 1_500_000
    assert {evidence.label for evidence in story.evidence} >= {
        "Memory",
        "Processor",
        "Price",
        "Below budget",
    }
    assert "Over budget" not in {product.name for product in story.candidates}
    assert "No stock" not in {product.name for product in story.candidates}


@pytest.mark.asyncio
async def test_hero_story_returns_none_when_no_orderable_laptop_exists(test_db):
    test_db.add(
        Product(
            name="Unavailable laptop",
            sku="HERO-UNAVAILABLE",
            category="laptops",
            price=5_000_000,
            stock_quantity=0,
            image_url="/laptop.jpg",
        )
    )
    await test_db.flush()

    assert await HeroStoryService(test_db).get_story() is None
