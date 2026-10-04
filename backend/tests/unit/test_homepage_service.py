"""Homepage shelves preserve catalog authority and public promotion privacy."""

from datetime import datetime, timedelta, timezone

import pytest

from src.models.product import Product
from src.models.promotion import Promotion
from src.services.homepage_service import HomepageService


@pytest.mark.asyncio
async def test_homepage_uses_active_imaged_stock_and_live_public_offers(test_db):
    test_db.add_all([
        Product(name="Available", sku="HOME-1", category="laptops", price=100,
                image_url="/product.png", stock_quantity=2),
        Product(name="Hidden", sku="HOME-2", category="laptops", price=100,
                image_url="/product.png", stock_quantity=2, is_active=False),
        Product(name="No stock", sku="HOME-3", category="beauty", price=100,
                image_url="/product.png", stock_quantity=0),
    ])
    now = datetime.now(timezone.utc)
    test_db.add_all([
        Promotion(name="Live offer", promotion_type="percentage", value=20,
                  starts_at=now-timedelta(days=1), ends_at=now+timedelta(days=1),
                  scope_type="all", active=True),
        Promotion(name="Expired offer", promotion_type="percentage", value=50,
                  starts_at=now-timedelta(days=2), ends_at=now-timedelta(days=1),
                  scope_type="all", active=True),
    ])
    await test_db.flush()
    homepage = await HomepageService(test_db).get_homepage()
    assert [product.name for product in homepage["featured"]] == ["Available"]
    assert [offer["name"] for offer in homepage["promotions"]] == ["Live offer"]
    assert "code" not in homepage["promotions"][0]
    assert {row["value"]: row["count"] for row in homepage["categories"]} == {
        "beauty": 1, "laptops": 1,
    }
    categories = {row["value"]: row for row in homepage["categories"]}
    assert categories["laptops"]["image_url"] == "/product.png"
    assert categories["beauty"]["image_url"] is None


@pytest.mark.asyncio
async def test_homepage_returns_three_editorial_rounds_for_guided_shortlists(test_db):
    categories = [
        "laptops", "smartphones", "headphones", "fashion", "home_living",
        "accessories", "beauty", "cameras", "footwear", "gaming",
        "home_appliances", "kitchen_appliances", "smartwatches", "tablets",
        "televisions",
    ]
    test_db.add_all([
        Product(
            name=f"{category} {variant}",
            sku=f"{category.upper()}-{variant}",
            category=category,
            price=5_000_000,
            image_url=f"/{category}-{variant}.jpg",
            stock_quantity=3,
        )
        for category in categories
        for variant in range(4)
    ])
    await test_db.flush()

    homepage = await HomepageService(test_db).get_homepage()

    assert [len(homepage[key]) for key in ("featured", "trending", "recommendations")] == [
        15, 15, 15,
    ]
    assert sum(
        product.category == "laptops"
        for key in ("featured", "trending", "recommendations")
        for product in homepage[key]
    ) == 3
