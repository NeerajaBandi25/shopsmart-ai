"""Hard/soft extraction and deterministic routing invariants."""

import pytest
from pydantic import ValidationError

from src.services.shopping_mission import ShoppingMission, extract_shopping_mission


def test_complex_developer_mission_preserves_stretch():
    mission = extract_shopping_mission(
        "I need a laptop for React, Python, Docker and occasional local AI. "
        "I commute often. I prefer under ₹75k but can stretch to ₹85k if worth it. "
        "No gaming-looking laptop."
    )
    assert mission.category == "laptops"
    assert mission.hard_constraints.max_budget_cents == 8500000
    assert mission.soft_constraints.preferred_budget_cents == 7500000
    assert mission.soft_constraints.portability
    assert mission.soft_constraints.professional_design
    assert set(mission.desired_use_cases) == {"software_development", "docker", "local_ai"}
    assert mission.execution_path == "LLM_PATH"
    assert not mission.clarification_needed


def test_simple_price_request_uses_fast_path():
    mission = extract_shopping_mission("Show laptops under ₹60,000")
    assert mission.hard_constraints.max_budget_cents == 6000000
    assert mission.execution_path == "FAST_PATH"


def test_one_useful_clarification():
    mission = extract_shopping_mission("I need a good laptop")
    assert mission.clarification_needed
    assert len(mission.clarification_questions) == 1


def test_refinement_preserves_budget_and_hardware_requirement():
    original = extract_shopping_mission("Laptop under 85k with at least 32 GB RAM")
    mission = extract_shopping_mission("Make it lighter", original.model_dump())
    assert mission.hard_constraints.max_budget_cents == 8500000
    assert mission.hard_constraints.min_ram_gb == 32
    assert mission.hard_constraints.min_budget_cents is None
    assert mission.soft_constraints.portability
    assert not original.soft_constraints.portability


def test_weight_is_not_money():
    mission = extract_shopping_mission("Laptop under 1.5 kg")
    assert mission.hard_constraints.max_budget_cents is None
    assert mission.hard_constraints.max_weight_kg == 1.5


def test_invalid_bounds_fail_closed():
    with pytest.raises(ValidationError):
        ShoppingMission(hard_constraints={"min_budget_cents": 500, "max_budget_cents": 100})
    with pytest.raises(ValidationError):
        ShoppingMission(performance_priorities={"cpu": float("nan")})


def test_weight_and_budget_do_not_collide():
    mission = extract_shopping_mission("Laptop under 85k and under 2 kg with at least 32 GB RAM")
    assert mission.hard_constraints.max_budget_cents == 8500000
    assert mission.hard_constraints.min_budget_cents is None
    assert mission.hard_constraints.max_weight_kg == 2


def test_natural_brand_exclusions_and_negated_gaming():
    mission = extract_shopping_mission(
        "Laptop under 85k. No Dell; avoid HP; not for gaming. Prefer Asus."
    )
    assert set(mission.hard_constraints.excluded_brands) == {"dell", "hp"}
    assert mission.soft_constraints.preferred_brands == ["asus"]
    assert "gaming" not in mission.desired_use_cases


def test_final_acceptance_mission():
    mission = extract_shopping_mission(
        "I'm a frontend developer moving into AI. I use React, Python and Docker "
        "and sometimes run models locally. I commute, so I don't want a huge laptop. "
        "I prefer staying under ₹75k, but show me one option up to ₹85k if the upgrade is worthwhile."
    )
    assert mission.hard_constraints.max_budget_cents == 8500000
    assert mission.soft_constraints.preferred_budget_cents == 7500000
    assert "local_ai" in mission.desired_use_cases
    assert mission.soft_constraints.portability


def test_professional_looking_is_a_soft_aesthetic_preference():
    mission = extract_shopping_mission(
        "Developer using React, Python and Docker. I commute and prefer a professional-looking laptop. "
        "Stay around 75k but stretch to 85k if the upgrade is worthwhile."
    )

    assert mission.hard_constraints.max_budget_cents == 8500000
    assert mission.soft_constraints.preferred_budget_cents == 7500000
    assert mission.soft_constraints.portability
    assert mission.soft_constraints.professional_design
    assert set(mission.desired_use_cases) == {"software_development", "docker"}


def test_external_constraint_text_bounded():
    with pytest.raises(ValidationError):
        ShoppingMission(hard_constraints={"required_features": ["x" * 121]})
