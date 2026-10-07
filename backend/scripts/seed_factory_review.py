"""Reproducible fictional browser fixtures, restricted to an isolated review DB."""

import argparse
import asyncio
import json
import os
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.engine import make_url

from src.core.config import settings
from src.database import AsyncSessionLocal
from src.models.product import Product
from src.seed.portfolio_catalog import build_catalog_products
from src.seed.production_like import SKU_PREFIX, seed_dataset
from src.services.assistant_knowledge import KnowledgeIngestionService

POLICY_CORPUS = (
    Path(__file__).parents[1] / "evals" / "datasets" / "local_shopsmart_knowledge_v1.json"
)


async def seed(apply: bool) -> None:
    target = make_url(settings.database_url)
    if (
        not apply
        or settings.app_env not in {"test", "local", "development"}
        or target.host not in {"127.0.0.1", "localhost", "::1"}
        or not (target.database or "").startswith("shopsmart_factory_review_")
    ):
        raise SystemExit("Refused: use --apply with an isolated loopback factory review DB.")
    password = os.environ.get("SHOPSMART_LOCAL_SEED_PASSWORD")
    if not password:
        raise SystemExit("Set a disposable SHOPSMART_LOCAL_SEED_PASSWORD for fictional accounts.")
    async with AsyncSessionLocal() as db:
        counts = await seed_dataset(db, password)
        policies = json.loads(POLICY_CORPUS.read_text(encoding="utf-8"))
        ingestion = KnowledgeIngestionService(db)
        for source in policies["sources"]:
            await ingestion.publish(**source)
        # Historical synthetic orders retain their rows. The visible catalog uses
        # the richer authored merchandise needed to evaluate hardware evidence.
        await db.execute(
            update(Product).where(Product.sku.startswith(SKU_PREFIX)).values(is_active=False)
        )
        existing = set((await db.scalars(select(Product.sku))).all())
        authored = build_catalog_products()
        for product in authored:
            if product.sku not in existing:
                db.add(product)
        await db.commit()
        print(
            {
                "synthetic_fixtures": counts,
                "local_demo_policy_sources": len(policies["sources"]),
                "authored_catalog": len(authored),
                "target": target.database,
            }
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    asyncio.run(seed(parser.parse_args().apply))
