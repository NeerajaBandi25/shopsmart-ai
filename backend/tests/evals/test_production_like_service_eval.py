import json

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.evals.production_like import evaluate_seeded_database
from src.seed.production_like import seed_dataset


@pytest.mark.asyncio
async def test_production_like_assistant_uses_seeded_services_and_owned_context(
    test_db: AsyncSession,
):
    await seed_dataset(test_db, "LocalOnly!2026")

    result = await evaluate_seeded_database(test_db)

    assert result["dataset_counts"]["products"] == 1000
    assert result["category_precision"] == {
        "laptops_under_60000": 1.0,
        "phones_under_30000": 1.0,
    }
    assert result["price_precision"]["products_under_5000"] == 1.0
    assert sum(result["category_distribution"].values()) == 1000
    assert result["scenario_count"] >= 20
    assert result["passed"], json.dumps(result, indent=2, sort_keys=True)
