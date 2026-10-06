"""Mission-dependent ranking and evidence/constraint invariants."""

from src.services.recommendation_ranking import rank_recommendations
from src.services.shopping_mission import ShoppingMission, extract_shopping_mission


def product(identity, price=7000000, **specifications):
    return {
        "id": identity,
        "category": "laptops",
        "brand": identity,
        "price": price,
        "stock_quantity": 4,
        "is_active": True,
        "specifications": specifications,
    }


def test_enforces_budget_ram_stock_and_missing_evidence():
    mission = extract_shopping_mission("Laptop under 85k with 32 GB RAM")
    products = [
        product("eligible", ram_gb=32),
        product("too-expensive", 9000000, ram_gb=32),
        product("too-small", ram_gb=16),
        product("unknown"),
    ]
    unavailable = product("unavailable", ram_gb=32)
    unavailable["stock_quantity"] = 0
    result = rank_recommendations([*products, unavailable], mission)
    assert [r.product_id for r in result.recommendations] == ["eligible"]
    assert result.eligible_count == 1
    assert not result.relaxations


def test_no_match_returns_disclosed_relaxation_without_recommendation():
    mission = extract_shopping_mission("Laptop under 60k with 32 GB RAM")
    result = rank_recommendations([product("alternative", 6500000, ram_gb=16)], mission)
    assert not result.recommendations
    assert result.relaxations[0].requires_confirmation
    assert set(result.relaxations[0].violated_constraints) == {"max_budget_cents", "min_ram_gb"}


def test_different_missions_change_best_fit():
    portable = product("portable", 7000000, ram_gb=16, cpu_cores=6, weight_kg=1.1, battery_hours=12)
    powerful = product("powerful", 7000000, ram_gb=32, cpu_cores=12, weight_kg=2.8, battery_hours=4)
    developer = extract_shopping_mission("Laptop under 85k for React Python Docker")
    student = extract_shopping_mission("Portable laptop under 85k for a student")
    assert rank_recommendations([portable, powerful], developer).labels["BEST_FIT"] == "powerful"
    assert rank_recommendations([portable, powerful], student).labels["BEST_FIT"] == "portable"


def test_seven_shopper_personas_produce_mission_specific_best_fit():
    catalog = [
        product(
            "value",
            4200000,
            ram_gb=16,
            cpu_cores=6,
            gpu_vram_gb=0,
            storage_gb=512,
            weight_kg=2.1,
            battery_hours=8,
        ),
        product(
            "traveler",
            7600000,
            ram_gb=16,
            cpu_cores=8,
            gpu_vram_gb=0,
            storage_gb=512,
            weight_kg=1.1,
            battery_hours=14,
        ),
        product(
            "creator",
            8500000,
            ram_gb=32,
            cpu_cores=12,
            gpu_vram_gb=4,
            storage_gb=2048,
            weight_kg=2.0,
            battery_hours=6,
        ),
        product(
            "gamer",
            7800000,
            ram_gb=16,
            cpu_cores=10,
            gpu_vram_gb=8,
            storage_gb=1024,
            weight_kg=2.5,
            battery_hours=5,
        ),
        product(
            "developer",
            7200000,
            ram_gb=32,
            cpu_cores=12,
            gpu_vram_gb=2,
            storage_gb=1024,
            weight_kg=1.8,
            battery_hours=7,
        ),
        product(
            "student",
            5800000,
            ram_gb=16,
            cpu_cores=8,
            gpu_vram_gb=0,
            storage_gb=512,
            weight_kg=1.5,
            battery_hours=12,
        ),
    ]
    missions = {
        "developer": extract_shopping_mission("Laptop under 90k for React development and Docker"),
        "student": extract_shopping_mission("Laptop under 70k for a student"),
        "local_ai": extract_shopping_mission("Laptop under 90k to run local AI models"),
        "traveler": extract_shopping_mission("Portable lightweight laptop under 90k for travel"),
        "budget": ShoppingMission(category="laptops", performance_priorities={"value": 6}),
        "casual_gamer": extract_shopping_mission("Casual gaming laptop under 90k"),
        "creator": extract_shopping_mission("Laptop under 90k for creative video editing"),
    }
    top_picks = {
        persona: rank_recommendations(catalog, mission).labels["BEST_FIT"]
        for persona, mission in missions.items()
    }

    assert len(set(top_picks.values())) >= 5
    assert top_picks["traveler"] == "traveler"
    assert top_picks["budget"] == "value"
    assert top_picks["casual_gamer"] == "gamer"
    assert top_picks["creator"] == "creator"
    assert top_picks["developer"] != top_picks["student"]


def test_reasons_trace_to_catalog_evidence_and_unknowns_are_disclosed():
    result = rank_recommendations(
        [product("one", RAM="32 GB RAM", Processor="6-core processor")],
        extract_shopping_mission("Laptop under 85k for Docker while commuting"),
    )
    rec = result.recommendations[0]
    assert any(e.field == "specifications.ram" and e.value == "32 GB RAM" for e in rec.evidence)
    assert "Catalog does not provide battery evidence" in rec.tradeoffs
    assert "Catalog does not provide weight evidence" in rec.tradeoffs
    assert not any("excellent" in reason.lower() for reason in rec.reasons)


def test_preferences_cannot_override_exclusion():
    mission = ShoppingMission(category="laptops", hard_constraints={"excluded_brands": ["a"]})
    result = rank_recommendations(
        [product("a"), product("b")], mission, personalization={"preferred_brands": ["a"]}
    )
    assert [r.product_id for r in result.recommendations] == ["b"]


def test_ties_stable_and_duplicates_do_not_inflate_candidates():
    mission = ShoppingMission(category="laptops")
    a, b = product("a"), product("b")
    result = rank_recommendations([b, a, a], mission)
    assert [r.product_id for r in result.recommendations] == ["a", "b"]
    assert result.candidate_count == 2


def test_best_value_is_included_when_it_falls_outside_the_requested_top_rank():
    mission = extract_shopping_mission("Laptop under 85k for React development and Docker")
    products = [
        product("high-spec", 8000000, ram_gb=32, cpu_cores=12, storage_gb=1024),
        product("middle-spec", 7000000, ram_gb=16, cpu_cores=8, storage_gb=512),
        product("budget", 2500000),
    ]

    result = rank_recommendations(products, mission, limit=2)
    recommendation_ids = {item.product_id for item in result.recommendations}

    assert result.labels["BEST_VALUE"] == "budget"
    assert result.labels["BEST_VALUE"] in recommendation_ids
    assert result.labels["BEST_FIT"] in recommendation_ids


def test_cpu_model_number_is_not_core_count_and_false_feature_is_not_supported():
    mission = ShoppingMission(category="laptops", hard_constraints={"required_features": ["oled"]})
    result = rank_recommendations(
        [product("a", Processor="Intel Core i7-1360P", oled=False)], mission
    )
    assert not result.recommendations
    relaxed = ShoppingMission(category="laptops")
    rec = rank_recommendations(
        [product("a", Processor="Intel Core i7-1360P")], relaxed
    ).recommendations[0]
    assert "cpu" not in rec.attribute_scores
