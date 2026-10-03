import json
from pathlib import Path

from src.evals.assistant_eval import evaluate_assistant_dataset


def test_versioned_commerce_routing_dataset_passes():
    dataset_path = Path(__file__).parents[2] / "evals" / "datasets" / "commerce_v1.json"
    result = evaluate_assistant_dataset(json.loads(dataset_path.read_text(encoding="utf-8")))

    assert result["assistant_case_count"] == 13.0
    assert result["assistant_intent_accuracy"] == 1.0
    assert result["catalog_filter_accuracy"] == 1.0
    assert result["category_filter_accuracy"] == 1.0


def test_production_like_commerce_routing_dataset_passes():
    dataset_path = (
        Path(__file__).parents[2] / "evals" / "datasets" / "commerce_production_like_v1.json"
    )
    result = evaluate_assistant_dataset(json.loads(dataset_path.read_text(encoding="utf-8")))

    assert result["assistant_case_count"] == 25.0
    assert result["assistant_intent_accuracy"] == 1.0
    assert result["catalog_filter_accuracy"] == 1.0
    assert result["category_filter_accuracy"] == 1.0
