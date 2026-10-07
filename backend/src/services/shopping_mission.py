"""Typed shopping intent. Budgets use the catalog's integer minor currency units."""

import re
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from src.models.product import PRODUCT_CATEGORIES
from src.services.assistant_router import CATEGORY_ALIASES

ConstraintText = Annotated[str, StringConstraints(min_length=1, max_length=120)]


class HardConstraints(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_budget_cents: int | None = Field(default=None, ge=0)
    min_budget_cents: int | None = Field(default=None, ge=0)
    min_ram_gb: int | None = Field(default=None, ge=1, le=1024)
    min_storage_gb: int | None = Field(default=None, ge=1)
    max_weight_kg: float | None = Field(default=None, gt=0)
    required_features: list[ConstraintText] = Field(default_factory=list, max_length=20)
    excluded_brands: list[ConstraintText] = Field(default_factory=list, max_length=20)
    in_stock_only: bool = True


class SoftConstraints(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preferred_budget_cents: int | None = Field(default=None, ge=0)
    preferred_brands: list[ConstraintText] = Field(default_factory=list, max_length=20)
    optional_features: list[ConstraintText] = Field(default_factory=list, max_length=20)
    portability: bool = False
    professional_design: bool = False


class ShoppingMission(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: str | None = None
    user_goal: str = Field(default="shopping", max_length=1000)
    hard_constraints: HardConstraints = Field(default_factory=HardConstraints)
    soft_constraints: SoftConstraints = Field(default_factory=SoftConstraints)
    desired_use_cases: list[ConstraintText] = Field(default_factory=list, max_length=20)
    performance_priorities: dict[str, float] = Field(default_factory=dict)
    aesthetic_preferences: list[ConstraintText] = Field(default_factory=list, max_length=20)
    urgency: ConstraintText | None = None
    confidence: float = Field(default=0.5, ge=0, le=1)
    clarification_needed: bool = False
    clarification_questions: list[Annotated[str, StringConstraints(max_length=500)]] = Field(
        default_factory=list, max_length=1
    )
    execution_path: Literal["FAST_PATH", "LLM_PATH"] = "LLM_PATH"
    version: str = "mission-v1"

    @model_validator(mode="after")
    def validate_bounds(self):
        hard = self.hard_constraints
        if (
            hard.min_budget_cents is not None
            and hard.max_budget_cents is not None
            and hard.min_budget_cents > hard.max_budget_cents
        ):
            raise ValueError("Minimum budget exceeds maximum budget")
        if self.category and self.category not in PRODUCT_CATEGORIES:
            raise ValueError("Unsupported mission category")
        if any(not 0 <= weight <= 10 for weight in self.performance_priorities.values()):
            raise ValueError("Priority weights must be finite and between zero and ten")
        return self


_AMOUNT = r"(?:₹|rs\.?|inr|\$)?\s*(\d+(?:,\d{2,3})*(?:\.\d{1,2})?)\s*(k|thousand|lakh)?\b"


def _money(match: re.Match) -> int:
    multiplier = {"k": 1000, "thousand": 1000, "lakh": 100000}.get(match.group(2), 1)
    return int(Decimal(match.group(1).replace(",", "")) * multiplier * 100)


def extract_shopping_mission(
    message: str, previous: ShoppingMission | dict[str, Any] | None = None
) -> ShoppingMission:
    """Conservative local extraction; complex missions still select LLM understanding.

    Explicit current-turn constraints override previous-turn preferences. Unknown
    product attributes never become inferred mandatory hardware requirements.
    """
    mission = (
        ShoppingMission.model_validate(previous).model_copy(deep=True)
        if previous is not None
        else ShoppingMission()
    )
    text = " ".join(message.lower().split())
    mission.user_goal = message[:1000]
    hard, soft = mission.hard_constraints, mission.soft_constraints
    for alias in sorted(CATEGORY_ALIASES, key=len, reverse=True):
        if re.search(rf"\b{re.escape(alias)}\b", text):
            mission.category = CATEGORY_ALIASES[alias]
            break
    if mission.category is None and re.search(r"\b(react|python|docker|developer)\b", text):
        mission.category = "laptops"
    nonmoney_unit = r"\s*(?:kg|grams?|gb|tb|ram|hours?|cores?|inches?)\b"
    upper = [
        m
        for m in re.finditer(
            r"(?:under|below|up to|at most|maximum|no more than)\s*" + _AMOUNT, text
        )
        if not re.match(nonmoney_unit, text[m.end() :])
    ]
    stretch = next(
        (
            m
            for m in re.finditer(r"(?:stretch(?:\s+to)?|up to)\s*" + _AMOUNT, text)
            if not re.match(nonmoney_unit, text[m.end() :])
        ),
        None,
    )
    preferred = re.search(
        r"(?:prefer(?:red)?(?:\s+staying)?(?:\s+under|\s+around)?|around|about)\s*" + _AMOUNT, text
    )
    if upper:
        hard.max_budget_cents = min(_money(m) for m in upper)
    if stretch:
        hard.max_budget_cents = _money(stretch)
        if upper:
            soft.preferred_budget_cents = min(_money(m) for m in upper)
    if preferred and not re.match(nonmoney_unit, text[preferred.end() :]):
        soft.preferred_budget_cents = _money(preferred)
    lower = re.search(r"(?:above|over|minimum|at least)\s*" + _AMOUNT, text)
    # Avoid treating 'at least 32 GB RAM' as a monetary floor.
    if lower and not re.match(nonmoney_unit, text[lower.end() :]):
        hard.min_budget_cents = _money(lower)
    ram = re.search(
        r"(?:at least\s+|minimum\s+|require(?:d)?\s+|must have\s+)?(\d+)\s*gb\s*(?:of\s+)?ram", text
    )
    if ram:
        hard.min_ram_gb = int(ram.group(1))
    storage = re.search(r"(\d+)\s*(gb|tb)\s*(?:ssd|storage)", text)
    if storage:
        hard.min_storage_gb = int(storage.group(1)) * (1024 if storage.group(2) == "tb" else 1)
    weight = re.search(r"(?:under|below|at most)\s*(\d+(?:\.\d+)?)\s*kg", text)
    if weight:
        hard.max_weight_kg = float(weight.group(1))
    workloads = {
        "software_development": r"\b(react|python|coding|developer|development|programming)\b",
        "docker": r"\bdocker\b",
        "local_ai": r"\b(local ai|local models|run models locally|inference)\b",
        "student": r"\b(student|college|school|studying)\b",
        "gaming": r"(?<!no )\bgaming\b(?![- ]looking)",
        "creative": r"\b(video editing|3d|rendering|creative)\b",
    }
    for name, pattern in workloads.items():
        if name == "gaming" and re.search(r"(?:not|no|don't|do not).*\bgaming\b", text):
            continue
        if re.search(pattern, text) and name not in mission.desired_use_cases:
            mission.desired_use_cases.append(name)
    if re.search(r"\b(commut\w*|travel\w*|portable|lightweight|lighter|not.*huge)\b", text):
        soft.portability = True
    if re.search(
        r"(?:no|not|don't want).*gaming[- ]looking|professional design|professional[- ]looking",
        text,
    ):
        soft.professional_design = True
        mission.aesthetic_preferences = ["professional_design"]
    for feature in ("oled", "touchscreen", "usb-c", "wifi 6"):
        if re.search(rf"(?:must have|required?|need)\s+(?:an?\s+)?{re.escape(feature)}\b", text):
            if feature not in hard.required_features:
                hard.required_features.append(feature)
        elif feature in text and feature not in soft.optional_features:
            soft.optional_features.append(feature)
    for prefix, destination in (
        (r"(?:exclude|avoid|no)\s+brand\s+", hard.excluded_brands),
        (r"prefer\s+brand\s+", soft.preferred_brands),
    ):
        brand = re.search(prefix + r"([\w-]+)", text)
        if brand and brand.group(1) not in destination:
            destination.append(brand.group(1))
    # Common brand names allow natural phrasing without misclassifying 'no gaming'.
    brands = r"dell|hp|lenovo|asus|acer|apple|samsung|msi|microsoft|vellune|orbiant|merroway"
    for prefix, destination in (
        (r"(?:exclude|avoid|no|not)\s+", hard.excluded_brands),
        (r"prefer(?:red)?\s+", soft.preferred_brands),
    ):
        for brand in re.finditer(prefix + rf"({brands})\b", text):
            if brand.group(1) not in destination:
                destination.append(brand.group(1))
    priorities = {"ram": 1.0, "cpu": 1.0, "value": 1.0}
    if "software_development" in mission.desired_use_cases or "docker" in mission.desired_use_cases:
        priorities.update(ram=3.0, cpu=3.0, storage=1.5)
    if "local_ai" in mission.desired_use_cases:
        priorities.update(ram=3.0, gpu=2.0)
    if "gaming" in mission.desired_use_cases:
        priorities.update(gpu=4.0, cpu=2.0)
    if "creative" in mission.desired_use_cases:
        priorities.update(ram=2.5, cpu=3.0, gpu=2.0, storage=3.0)
    if "student" in mission.desired_use_cases:
        priorities.update(value=3.0, battery=2.0)
    if soft.portability:
        priorities.update(weight=3.0, battery=2.0)
    mission.performance_priorities = priorities
    mission.urgency = (
        "soon" if re.search(r"\b(urgent|today|tomorrow|asap)\b", text) else mission.urgency
    )
    mission.clarification_needed = bool(
        mission.category
        and not mission.desired_use_cases
        and hard.max_budget_cents is None
        and soft.preferred_budget_cents is None
    )
    mission.clarification_questions = (
        ["What's your main use and approximate budget?"] if mission.clarification_needed else []
    )
    mission.confidence = 0.9 if mission.category and (upper or mission.desired_use_cases) else 0.55
    mission.execution_path = (
        "FAST_PATH"
        if mission.category
        and not mission.desired_use_cases
        and upper
        and not soft.portability
        and not soft.optional_features
        and not hard.required_features
        else "LLM_PATH"
    )
    return ShoppingMission.model_validate(mission.model_dump())


def mission_catalog_filters(mission: ShoppingMission) -> dict[str, Any]:
    """Candidate generation only; ranking enforces every hard attribute constraint."""
    return {
        "category": mission.category,
        "min_price_cents": mission.hard_constraints.min_budget_cents,
        "max_price_cents": mission.hard_constraints.max_budget_cents,
        "in_stock_only": mission.hard_constraints.in_stock_only,
    }
