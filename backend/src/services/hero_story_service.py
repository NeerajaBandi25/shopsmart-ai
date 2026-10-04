"""Backend-grounded laptop shortlist for the homepage's guided shopping story."""

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.product import Product
from src.schemas.product import HeroEvidence, HeroStoryResponse, ProductResponse

BRIEF = "Best laptop for coding and local AI under ₹70,000"
BUDGET_MINOR = 7_000_000
SHORTLIST_SIZE = 3


def _memory_gb(product: Product) -> int:
    value = (product.specifications or {}).get("RAM", "")
    match = re.search(r"(\d+)\s*GB", str(value), re.IGNORECASE)
    return int(match.group(1)) if match else 0


def _storage_gb(product: Product) -> int:
    value = (product.specifications or {}).get("Storage", "")
    match = re.search(r"(\d+)\s*(TB|GB)", str(value), re.IGNORECASE)
    if not match:
        return 0
    amount = int(match.group(1))
    return amount * 1024 if match.group(2).upper() == "TB" else amount


class HeroStoryService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_story(self) -> HeroStoryResponse | None:
        rows = (
            await self.db.execute(
                select(Product)
                .where(
                    Product.is_active.is_(True),
                    Product.stock_quantity > 0,
                    Product.category == "laptops",
                    Product.price <= BUDGET_MINOR,
                    Product.image_url.is_not(None),
                )
                .order_by(Product.price, Product.id)
                .limit(600)
            )
        ).scalars().all()

        # Prefer 16 GB+ configurations for development; only widen when the
        # catalog cannot supply three distinct, image-backed product families.
        qualified = [product for product in rows if _memory_gb(product) >= 16]
        pool = qualified or rows
        products_by_image: dict[str, list[Product]] = {}
        for product in pool:
            products_by_image.setdefault(product.image_url or str(product.id), []).append(product)

        families = sorted(
            products_by_image.values(),
            key=lambda family: min((product.price, str(product.id)) for product in family),
        )[:SHORTLIST_SIZE]
        family_representatives = [
            min(family, key=lambda product: (product.price, str(product.id)))
            for family in families
        ]
        if not family_representatives:
            return None

        best_value = min(
            family_representatives,
            key=lambda product: (product.price, str(product.id)),
        )
        candidates = [best_value]
        for family in families:
            if family[0].image_url == best_value.image_url:
                continue
            alternatives = sorted(family, key=lambda product: (product.price, str(product.id)))
            # For local model files, more storage can be a meaningful tradeoff.
            # Prefer the lowest-priced capacity variation when the catalog lists one.
            representative = next(
                (
                    product
                    for product in alternatives
                    if _storage_gb(product) > _storage_gb(best_value)
                ),
                alternatives[0],
            )
            candidates.append(representative)

        candidates.sort(key=lambda product: (product.price, str(product.id)))
        if not candidates:
            return None

        max_memory = max(_memory_gb(product) for product in candidates)
        best_fit = min(
            (product for product in candidates if _memory_gb(product) == max_memory),
            key=lambda product: (product.price, str(product.id)),
        )
        evidence = [
            HeroEvidence(label=label, value=str(value))
            for label, value in (
                ("Memory", (best_fit.specifications or {}).get("RAM")),
                ("Processor", (best_fit.specifications or {}).get("Processor")),
                ("Graphics", (best_fit.specifications or {}).get("Graphics")),
                ("Storage", (best_fit.specifications or {}).get("Storage")),
                ("Price", f"₹{best_fit.price / 100:,.0f}"),
                ("Below budget", f"₹{(BUDGET_MINOR - best_fit.price) / 100:,.0f}"),
            )
            if value is not None
        ]
        reason = (
            f"Lowest-priced {max_memory} GB option in this shortlist at "
            f"₹{best_fit.price / 100:,.0f} — "
            f"₹{(BUDGET_MINOR - best_fit.price) / 100:,.0f} below your budget."
        )
        return HeroStoryResponse(
            query=BRIEF,
            budget_minor=BUDGET_MINOR,
            candidates=[ProductResponse.model_validate(product) for product in candidates],
            recommended_product_id=best_fit.id,
            recommendation=reason,
            evidence=evidence,
            savings_minor=BUDGET_MINOR - best_fit.price,
        )
