"""Deterministic commerce ranking over authoritative, supplied catalog records.

Missing attributes are unknown, never guessed from a product's name or an LLM.
Scores describe this mission, not benchmark or future-proof performance claims.
"""

import math
import re
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, Field

from src.services.shopping_mission import ShoppingMission


class RecommendationEvidence(BaseModel):
    field: str
    value: Any
    source: str = "catalog"


class RecommendationResult(BaseModel):
    product_id: str
    overall_score: float
    constraint_score: float = 100
    workload_score: float
    preference_score: float
    value_score: float
    personalization_score: float
    penalties: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    tradeoffs: list[str] = Field(default_factory=list)
    evidence: list[RecommendationEvidence] = Field(default_factory=list)
    attribute_scores: dict[str, float] = Field(default_factory=dict)
    rank: int = 0
    labels: list[str] = Field(default_factory=list)
    ranking_version: str = "ranking-v1"


class RelaxationSuggestion(BaseModel):
    product_id: str
    violated_constraints: list[str]
    evidence: list[RecommendationEvidence]
    requires_confirmation: bool = True
    message: str = "This alternative does not satisfy every hard constraint. Confirm a change before choosing it."


class RankingResult(BaseModel):
    recommendations: list[RecommendationResult] = Field(default_factory=list)
    relaxations: list[RelaxationSuggestion] = Field(default_factory=list)
    labels: dict[str, str] = Field(default_factory=dict)
    candidate_count: int = 0
    eligible_count: int = 0
    ranking_version: str = "ranking-v1"


def _get(product: Any, field: str, default=None):
    return (
        product.get(field, default)
        if isinstance(product, Mapping)
        else getattr(product, field, default)
    )


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(value) else None
    if isinstance(value, str):
        match = re.search(r"\d+(?:\.\d+)?", value)
        return float(match.group()) if match else None
    return None


def _attributes(product: Any) -> tuple[dict[str, float], dict[str, Any]]:
    specs = _get(product, "specifications", {}) or {}
    raw = {str(key).lower().replace(" ", "_"): value for key, value in specs.items()}
    aliases = {
        "ram": ("ram_gb", "ram", "memory"),
        "storage": ("storage_gb", "storage", "ssd"),
        "cpu": ("cpu_cores", "processor_cores", "processor"),
        "gpu": ("vram_gb", "gpu_vram_gb", "graphics", "gpu"),
        "weight": ("weight_kg", "weight"),
        "battery": ("battery_hours", "battery_life_hours", "battery_life"),
    }
    numbers, evidence = {}, {}
    for attribute, keys in aliases.items():
        for key in keys:
            if key not in raw:
                continue
            value = raw[key]
            numeric = _number(value)
            # Never interpret CPU model numbers or battery capacity as performance.
            if attribute == "cpu" and key == "processor":
                match = re.search(r"(\d+)\s*[- ]?core", str(value), re.I)
                numeric = float(match.group(1)) if match else None
            if (
                attribute == "battery"
                and isinstance(value, str)
                and not re.search(r"hour|\bhr|\bh\b", value, re.I)
            ):
                numeric = None
            if attribute == "gpu" and key in {"graphics", "gpu"}:
                numeric = (
                    4.0
                    if "dedicated" in str(value).lower()
                    else 0.5
                    if "integrated" in str(value).lower()
                    else None
                )
            if numeric is not None and numeric >= 0:
                if attribute == "storage" and "tb" in str(value).lower():
                    numeric *= 1024
                if attribute == "weight" and isinstance(value, str) and re.search(r"\bg\b", value):
                    numeric /= 1000
                numbers[attribute] = numeric
                evidence[attribute] = {"field": f"specifications.{key}", "value": value}
            break
    return numbers, {**raw, "_numeric_evidence": evidence}


def _feature_present(raw: dict, feature: str) -> bool:
    wanted = feature.lower().replace("-", " ").replace("_", " ")
    for key, value in raw.items():
        if key.startswith("_") or value is False or value is None:
            continue
        content = f"{key} {value}".lower().replace("-", " ").replace("_", " ")
        if wanted in content:
            return True
    return False


def constraint_violations(product: Any, mission: ShoppingMission) -> list[str]:
    """Fail closed when authoritative evidence for a mandatory attribute is absent."""
    hard = mission.hard_constraints
    violations = []
    price = _number(_get(product, "price", _get(product, "price_cents")))
    if price is None or price < 0:
        violations.append("price_unavailable")
    if mission.category and _get(product, "category") != mission.category:
        violations.append("category")
    if price is not None:
        if hard.max_budget_cents is not None and price > hard.max_budget_cents:
            violations.append("max_budget_cents")
        if hard.min_budget_cents is not None and price < hard.min_budget_cents:
            violations.append("min_budget_cents")
    if str(_get(product, "brand", "")).lower() in {b.lower() for b in hard.excluded_brands}:
        violations.append("excluded_brands")
    if not _get(product, "is_active", True):
        violations.append("inactive")
    stock = _number(_get(product, "stock_quantity"))
    if hard.in_stock_only and (stock is None or stock <= 0):
        violations.append("availability")
    attrs, raw = _attributes(product)
    for field, attribute, bound, minimum in (
        ("min_ram_gb", "ram", hard.min_ram_gb, True),
        ("min_storage_gb", "storage", hard.min_storage_gb, True),
        ("max_weight_kg", "weight", hard.max_weight_kg, False),
    ):
        value = attrs.get(attribute)
        if bound is not None and (value is None or (value < bound if minimum else value > bound)):
            violations.append(field)
    for feature in hard.required_features:
        if not _feature_present(raw, feature):
            violations.append(f"required_feature:{feature}")
    return violations


def _evidence(product: Any) -> list[RecommendationEvidence]:
    result = []
    for field in ("price", "category", "brand", "stock_quantity"):
        value = _get(product, field, _get(product, "price_cents") if field == "price" else None)
        if value is not None:
            result.append(RecommendationEvidence(field=field, value=value))
    _, raw = _attributes(product)
    result.extend(RecommendationEvidence(**entry) for entry in raw["_numeric_evidence"].values())
    return result


def rank_recommendations(
    products: Sequence[Any],
    mission: ShoppingMission,
    personalization: Mapping[str, Any] | None = None,
    limit: int = 6,
) -> RankingResult:
    """Bounded explainable scoring with stable ties and a small diversity penalty.

    Only explicit, authorized preferences should be passed as personalization.
    A preference cannot override mission hard constraints.
    """
    limit = max(1, min(limit, 20))
    unique = {str(_get(p, "id", _get(p, "product_id", ""))): p for p in products}
    unique.pop("", None)
    eligible, rejected = [], []
    for product in unique.values():
        violations = constraint_violations(product, mission)
        (rejected if violations else eligible).append((product, violations))
    result = RankingResult(candidate_count=len(unique), eligible_count=len(eligible))
    if not eligible:
        for product, violations in sorted(
            rejected,
            key=lambda row: (len(row[1]), str(_get(row[0], "id", _get(row[0], "product_id", "")))),
        ):
            if any(
                v
                in {"category", "availability", "inactive", "price_unavailable", "excluded_brands"}
                for v in violations
            ):
                continue
            result.relaxations.append(
                RelaxationSuggestion(
                    product_id=str(_get(product, "id", _get(product, "product_id"))),
                    violated_constraints=violations,
                    evidence=_evidence(product),
                )
            )
            if len(result.relaxations) == 3:
                break
        return result
    weights = mission.performance_priorities or {"ram": 1, "cpu": 1, "value": 1}
    caps = {"ram": 32, "cpu": 12, "gpu": 8, "storage": 1024, "battery": 12}
    max_price = max(float(_get(p, "price", _get(p, "price_cents"))) for p, _ in eligible)
    preferred = mission.soft_constraints.preferred_budget_cents
    scores, catalog = [], {}
    for product, _ in eligible:
        product_id = str(_get(product, "id", _get(product, "product_id")))
        catalog[product_id] = product
        price = float(_get(product, "price", _get(product, "price_cents")))
        attrs, raw = _attributes(product)
        normalized = {key: min(value / caps[key], 1) for key, value in attrs.items() if key in caps}
        if "weight" in attrs:
            normalized["weight"] = max(0, min(1, (3 - attrs["weight"]) / 2))
        value = max(0, 1 - price / (max_price * 1.25)) if max_price else 1
        normalized["value"] = value
        denominator = sum(weight for key, weight in weights.items() if key != "value")
        workload = (
            sum(
                normalized.get(key, 0) * weight for key, weight in weights.items() if key != "value"
            )
            / denominator
            if denominator
            else 0
        )
        brand = str(_get(product, "brand", "")).lower()
        soft = mission.soft_constraints
        pref_scores = []
        if preferred is not None:
            pref_scores.append(
                1 if price <= preferred else max(0, preferred / max(price, 1) - 0.25)
            )
        if soft.preferred_brands:
            pref_scores.append(float(brand in {b.lower() for b in soft.preferred_brands}))
        if soft.portability:
            pref_scores.append(normalized.get("weight", 0))
        if soft.professional_design:
            design = str(raw.get("design", raw.get("aesthetic", ""))).lower()
            pref_scores.append(float("professional" in design or "minimal" in design))
        pref_scores.extend(float(_feature_present(raw, f)) for f in soft.optional_features)
        preference = sum(pref_scores) / len(pref_scores) if pref_scores else 0.5
        personal = 0.5
        if personalization and personalization.get("preferred_brands"):
            personal = float(brand in {str(b).lower() for b in personalization["preferred_brands"]})
        value_weight = min(0.4, 0.15 * weights.get("value", 1))
        overall = 100 * (
            (0.7 - value_weight) * workload
            + value_weight * value
            + 0.25 * preference
            + 0.05 * personal
        )
        reasons = ["Matches all verified hard constraints"]
        tradeoffs, penalties = [], []
        for key in ("ram", "cpu", "storage", "gpu", "battery", "weight"):
            if key in attrs:
                entry = raw["_numeric_evidence"][key]
                reasons.append(f"Catalog {entry['field'].split('.')[-1]}: {entry['value']}")
            elif key in weights:
                tradeoffs.append(f"Catalog does not provide {key} evidence")
        if preferred is not None and price > preferred:
            tradeoffs.append(
                f"INR {(price - preferred) / 100:,.2f} above preferred budget, within hard maximum"
            )
            penalties.append("above_preferred_budget")
        if soft.professional_design and "design" not in raw and "aesthetic" not in raw:
            tradeoffs.append("Professional design preference is unverified")
        scores.append(
            RecommendationResult(
                product_id=product_id,
                overall_score=round(overall, 2),
                workload_score=round(workload * 100, 2),
                preference_score=round(preference * 100, 2),
                value_score=round(value * 100, 2),
                personalization_score=round(personal * 100, 2),
                reasons=reasons,
                tradeoffs=tradeoffs,
                penalties=penalties,
                evidence=_evidence(product),
                attribute_scores={k: round(v * 100, 2) for k, v in normalized.items()},
            )
        )
    scores.sort(key=lambda r: (-r.overall_score, r.product_id))
    labels = {
        "BEST_FIT": scores[0].product_id,
        "BEST_VALUE": max(scores, key=lambda r: (r.value_score, r.overall_score)).product_id,
        "BEST_PERFORMANCE": max(
            scores, key=lambda r: (r.workload_score, r.overall_score)
        ).product_id,
        "BEST_BUDGET": min(
            scores,
            key=lambda r: (
                float(
                    _get(catalog[r.product_id], "price", _get(catalog[r.product_id], "price_cents"))
                ),
                r.product_id,
            ),
        ).product_id,
    }
    ranked_scores = list(scores)
    # Small diversity adjustment only after the best-fit has been selected.
    selected, brands = [], {}
    while scores and len(selected) < limit:
        chosen = max(
            scores,
            key=lambda r: (
                r.overall_score - 2 * brands.get(str(_get(catalog[r.product_id], "brand", "")), 0),
                -scores.index(r),
            ),
        )
        scores.remove(chosen)
        brand = str(_get(catalog[chosen.product_id], "brand", ""))
        brands[brand] = brands.get(brand, 0) + 1
        chosen.rank = len(selected) + 1
        chosen.labels = [key for key, value in labels.items() if value == chosen.product_id]
        selected.append(chosen)
    priority_label_names = ("BEST_FIT", "BEST_VALUE", "BEST_PERFORMANCE", "BEST_BUDGET")
    protected_ids = list(dict.fromkeys(labels[name] for name in priority_label_names))[:limit]
    for product_id in protected_ids:
        if any(item.product_id == product_id for item in selected):
            continue
        candidate = next(item for item in ranked_scores if item.product_id == product_id)
        replace_index = next(
            (
                index
                for index in range(len(selected) - 1, -1, -1)
                if selected[index].product_id not in protected_ids
            ),
            None,
        )
        if replace_index is None:
            continue
        selected.pop(replace_index)
        selected.append(candidate)
    for index, recommendation in enumerate(selected, start=1):
        recommendation.rank = index
        recommendation.labels = [
            key for key, value in labels.items() if value == recommendation.product_id
        ]
    result.recommendations = selected
    result.labels = {
        key: value for key, value in labels.items() if any(r.product_id == value for r in selected)
    }
    return result
