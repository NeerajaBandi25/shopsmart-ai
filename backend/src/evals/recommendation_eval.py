"""Run the versioned ranking cases against an isolated seeded ShopSmart catalog."""

import argparse
import asyncio
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.core.config import settings
from src.models.product import Product
from src.services.recommendation_ranking import constraint_violations, rank_recommendations
from src.services.shopping_mission import ShoppingMission

DATASET = Path(__file__).parents[2] / "evals" / "datasets" / "recommendation_scenarios_v1.json"


async def run_evaluation() -> dict:
    target = make_url(settings.database_url)
    if (
        settings.app_env.lower() not in {"local", "development", "dev", "test"}
        or not target.database
        or not target.database.startswith("shopsmart_factory_review_")
        or target.host not in {"127.0.0.1", "localhost", "::1"}
    ):
        raise RuntimeError(
            "Ranking evaluation requires the isolated loopback factory review database."
        )
    cases = json.loads(DATASET.read_text(encoding="utf-8"))["cases"]
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    constraint_checks = evidence_checks = stable_checks = scenario_count = actual_slots = 0
    category_coverage: dict[str, int] = {}
    try:
        async with factory() as db:
            for case in cases:
                mission = ShoppingMission(
                    category=case["category"],
                    hard_constraints={"max_budget_cents": case["budget"]},
                    performance_priorities={
                        {
                            "low_price": "value",
                            "low_weight": "weight",
                            "prefer_weight": "weight",
                        }.get(key.removeprefix("prefer_"), key.removeprefix("prefer_")): 3.0
                        for key, value in case.items()
                        if key.startswith("prefer_")
                        and value is not False
                        and value is not None
                        and key.removeprefix("prefer_")
                        in {
                            "cpu",
                            "gpu",
                            "ram",
                            "storage",
                            "battery",
                            "weight",
                            "low_price",
                            "low_weight",
                            "prefer_weight",
                            "value",
                        }
                    },
                )
                products = list(
                    (
                        await db.scalars(
                            select(Product)
                            .where(
                                Product.is_active.is_(True),
                                Product.category == mission.category,
                                Product.stock_quantity > 0,
                                Product.price <= case["budget"],
                            )
                            .order_by(Product.id)
                            .limit(100)
                        )
                    ).all()
                )
                ranking = rank_recommendations(products, mission)
                repeated = rank_recommendations(products, mission)
                actual_slots += len(ranking.recommendations)
                assert [r.product_id for r in ranking.recommendations] == [
                    r.product_id for r in repeated.recommendations
                ]
                stable_checks += 1
                scenario_count += 1
                category_coverage[mission.category] = category_coverage.get(mission.category, 0) + 1
                constraint_checks += sum(
                    not constraint_violations(
                        next(item for item in products if str(item.id) == result.product_id),
                        mission,
                    )
                    for result in ranking.recommendations
                )
                evidence_checks += sum(
                    any(
                        item.field == "price"
                        and item.value
                        == next(
                            product.price
                            for product in products
                            if str(product.id) == result.product_id
                        )
                        for item in result.evidence
                    )
                    for result in ranking.recommendations
                )
    finally:
        await engine.dispose()
    expected = actual_slots
    return {
        "dataset": "recommendation-scenarios-v1",
        "case_count": scenario_count,
        "category_coverage": category_coverage,
        "ranking_stability_accuracy": stable_checks / scenario_count if scenario_count else 1.0,
        "hard_constraint_satisfaction": constraint_checks / expected if expected else 1.0,
        "price_evidence_accuracy": evidence_checks / expected if expected else 1.0,
        "expected_top_six_slots": expected,
        "categories_with_candidates": sum(1 for count in category_coverage.values() if count > 0),
        "passed": scenario_count == len(cases)
        and stable_checks == scenario_count
        and constraint_checks == expected
        and evidence_checks == expected,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = asyncio.run(run_evaluation())
    encoded = json.dumps(result, indent=2, sort_keys=True)
    print(encoded)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
