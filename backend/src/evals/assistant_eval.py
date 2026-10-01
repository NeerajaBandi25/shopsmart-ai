"""Evaluate deterministic assistant routing and supported catalog filters."""

from src.services.assistant_router import route_assistant_message


def evaluate_assistant_dataset(dataset: dict) -> dict[str, float]:
    cases = dataset["cases"]
    if not cases:
        return {
            "assistant_case_count": 0.0,
            "assistant_intent_accuracy": 1.0,
            "catalog_filter_accuracy": 1.0,
            "category_filter_accuracy": 1.0,
        }
    intent_passes = 0
    filter_cases = 0
    filter_passes = 0
    category_cases = 0
    category_passes = 0
    for case in cases:
        route = route_assistant_message(case["question"])
        intent_passes += route.intent.value == case["intent"]
        filter_fields = {
            "category",
            "min_price_cents",
            "max_price_cents",
            "in_stock_only",
            "invalid_price_filter",
        }
        if filter_fields.intersection(case):
            filter_cases += 1
            filter_passes += (
                route.category == case.get("category")
                and route.min_price_cents == case.get("min_price_cents")
                and route.max_price_cents == case.get("max_price_cents")
                and route.in_stock_only is case.get("in_stock_only", False)
                and route.invalid_price_filter is case.get("invalid_price_filter", False)
            )
        if "category" in case:
            category_cases += 1
            category_passes += route.category == case["category"]
    return {
        "assistant_case_count": float(len(cases)),
        "assistant_intent_accuracy": intent_passes / len(cases),
        "catalog_filter_accuracy": filter_passes / filter_cases if filter_cases else 1.0,
        "category_filter_accuracy": category_passes / category_cases if category_cases else 1.0,
    }
