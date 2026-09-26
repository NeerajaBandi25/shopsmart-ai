"""Explicitly seed fictional products into a local ShopSmart database."""

import argparse
import asyncio
import os
import sys
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.models.product import Product


@dataclass(frozen=True)
class DemoProduct:
    name: str
    description: str
    sku: str
    price: int
    stock_quantity: int
    max_purchase_quantity: int = 5


DEMO_PRODUCTS = (
    DemoProduct(
        name="Northstar Everyday Backpack 20L",
        description="A lightweight fictional daypack with padded laptop storage.",
        sku="DEMO-BAG-020",
        price=6499,
        stock_quantity=24,
    ),
    DemoProduct(
        name="Harbor Ceramic Travel Mug",
        description="A fictional insulated mug with a spill-resistant lid.",
        sku="DEMO-MUG-012",
        price=2499,
        stock_quantity=38,
    ),
    DemoProduct(
        name="Juniper USB-C Desk Lamp",
        description="A fictional adjustable desk lamp with three brightness levels.",
        sku="DEMO-LAMP-003",
        price=3899,
        stock_quantity=17,
    ),
    DemoProduct(
        name="Daybreak Wireless Mouse",
        description="A fictional rechargeable wireless mouse for everyday work.",
        sku="DEMO-MOUSE-014",
        price=3299,
        stock_quantity=31,
    ),
    DemoProduct(
        name="Summit 65W USB-C Charger",
        description="A fictional compact charger for compatible phones and laptops.",
        sku="DEMO-CHARGER-065",
        price=4499,
        stock_quantity=22,
    ),
    DemoProduct(
        name="Willow Cotton Throw Blanket",
        description="A fictional soft cotton throw sized for a sofa or reading chair.",
        sku="DEMO-THROW-001",
        price=5899,
        stock_quantity=12,
    ),
    DemoProduct(
        name="Orbit Bluetooth Speaker",
        description="A fictional portable speaker with a built-in carry loop.",
        sku="DEMO-SPEAKER-008",
        price=7299,
        stock_quantity=16,
    ),
    DemoProduct(
        name="Meadow Stainless Water Bottle",
        description="A fictional double-wall bottle with a leak-resistant cap.",
        sku="DEMO-BOTTLE-024",
        price=2199,
        stock_quantity=29,
    ),
)


async def seed_missing_products(session: AsyncSession) -> int:
    """Insert demo products whose stable SKUs are not already present."""
    skus = [product.sku for product in DEMO_PRODUCTS]
    result = await session.execute(select(Product.sku).where(Product.sku.in_(skus)))
    existing_skus = set(result.scalars().all())
    missing_products = [
        Product(
            name=product.name,
            description=product.description,
            sku=product.sku,
            price=product.price,
            stock_quantity=product.stock_quantity,
            max_purchase_quantity=product.max_purchase_quantity,
        )
        for product in DEMO_PRODUCTS
        if product.sku not in existing_skus
    ]
    session.add_all(missing_products)
    await session.flush()
    return len(missing_products)


async def run_seed(
    apply: bool,
    allow_demo_seeding: str | None,
    *,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> int:
    """Run only when both explicit local-seeding safeguards are enabled."""
    if not apply or allow_demo_seeding != "true":
        print(
            "Demo seeding refused; no changes made. Pass --apply and set "
            "SHOPSMART_ALLOW_DEMO_SEEDING=true."
        )
        return 2

    try:
        if session_factory is None:
            from src.database import AsyncSessionLocal

            session_factory = AsyncSessionLocal

        async with session_factory() as session:
            inserted_count = await seed_missing_products(session)
            await session.commit()
    except Exception as error:
        print(
            f"Demo seeding failed ({type(error).__name__}); "
            "connection details were suppressed.",
            file=sys.stderr,
        )
        return 1

    print(f"Demo products complete: {inserted_count} inserted; existing SKUs unchanged.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="allow inserts when SHOPSMART_ALLOW_DEMO_SEEDING=true is also set",
    )
    args = parser.parse_args(argv)
    return asyncio.run(
        run_seed(args.apply, os.environ.get("SHOPSMART_ALLOW_DEMO_SEEDING"))
    )


if __name__ == "__main__":
    raise SystemExit(main())
