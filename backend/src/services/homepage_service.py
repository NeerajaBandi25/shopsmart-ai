"""Bounded public merchandising from active catalog records, never model output."""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.product import Product
from src.models.promotion import Promotion
from src.schemas.product import ProductResponse


class HomepageService:
    """Return discovery shelves and public offers; private coupon eligibility stays in cart.

    Shelves are deterministic editorial selections, not fabricated popularity metrics.
    Only active, orderable records with supplied images enter the homepage composition.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_homepage(self) -> dict:
        category_rows = (await self.db.execute(
            select(Product.category, func.count(Product.id))
            .where(Product.is_active.is_(True), Product.category.is_not(None))
            .group_by(Product.category).order_by(Product.category)
        )).all()
        products = (await self.db.execute(
            select(Product).where(
                Product.is_active.is_(True), Product.stock_quantity > 0,
                Product.image_url.is_not(None),
            ).order_by(Product.category, Product.name, Product.id).limit(1500)
        )).scalars().all()
        # Interleave categories so the homepage is a discovery surface rather than
        # a page of near-identical SKU variants from the newest seed batch.
        groups: dict[str, list[Product]] = {}
        for product in products:
            group = groups.setdefault(product.category or "other", [])
            if not any(item.image_url == product.image_url for item in group):
                group.append(product)

        def category_art(category: str) -> dict[str, str | None]:
            product = next(iter(groups.get(category, [])), None)
            return {
                "image_url": product.image_url if product else None,
                "image_alt": product.image_alt if product else None,
            }

        selections = []
        editorial_order = ["laptops", "smartphones", "headphones", "fashion", "home_living"]
        category_order = [category for category in editorial_order if category in groups]
        category_order.extend(category for category in groups if category not in category_order)
        for index in range(4):
            for category in category_order:
                group = groups[category]
                if index < len(group):
                    selections.append(group[index])
        now = datetime.now(timezone.utc)
        offers = (await self.db.execute(
            select(Promotion).where(
                Promotion.active.is_(True), Promotion.eligible_user_id.is_(None),
                Promotion.starts_at <= now, Promotion.ends_at > now,
            ).order_by(Promotion.ends_at, Promotion.id).limit(6)
        )).scalars().all()
        def serialize(rows: list[Product]) -> list[ProductResponse]:
            return [ProductResponse.model_validate(row) for row in rows]

        return {
            "categories": [
                {
                    "value": category,
                    "label": category.replace("_", " ").title(),
                    "count": count,
                    # Use an actual product image from this category so the
                    # category discovery art stays tied to the live catalog.
                    **category_art(category),
                }
                for category, count in category_rows
            ],
            # Return three complete editorial rounds. The page still renders
            # compact shelves, while its guided finder can work from the full
            # image-backed candidate pool instead of only the first 24 rows.
            "featured": serialize(selections[:15]),
            "trending": serialize(selections[15:30]),
            "recommendations": serialize(selections[30:45]),
            "promotions": [{"name": offer.name, "description": offer.description,
                            "discount_type": offer.promotion_type, "discount_value": offer.value,
                            "ends_at": offer.ends_at, "scope_category": offer.scope_category}
                           for offer in offers],
        }
