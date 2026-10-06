import json
from pathlib import Path

from src.evals.runner import aggregate, baseline_passes, load_dataset, score_case
from src.services.assistant_runtime import input_violation
from src.services.commerce_assistant import CommerceAssistantService

DATASET = Path(__file__).parents[2] / "evals" / "datasets" / "golden_v1.json"


def test_golden_dataset_is_versioned_and_covers_safety_cases():
    dataset = load_dataset(DATASET)
    assert dataset["version"] == "golden-v1"
    ids = {case["id"] for case in dataset["cases"]}
    assert {"easy-001", "auth-001", "injection-001", "empty-001"} <= ids


def test_eval_metrics_detect_unauthorized_retrieval_and_no_answer_regression():
    auth_case = {"authorized": False, "answerable": False, "expected_chunk_ids": []}
    score = score_case(auth_case, ["private-chunk"], True, ["source-1"])
    assert score["unauthorized_retrieval"] == 1.0
    assert score["no_answer_accuracy"] == 0.0
    assert aggregate([score])["unauthorized_retrieval"] == 1.0


def test_eval_metrics_measure_actual_retrieval_misses():
    case = {"authorized": True, "answerable": True, "expected_chunk_ids": ["chunk-return"]}
    score = score_case(case, [], False, [])
    assert score["retrieval_recall_at_5"] == 0.0
    assert score["no_answer_accuracy"] == 0.0


def test_zero_leakage_gate_rejects_positive_rate_and_missing_measurements():
    accepted = {"unauthorized_retrieval": 0.0, "prompt_injection_success": 0.0}
    assert baseline_passes({key: 0.0 for key in accepted}, accepted)
    assert not baseline_passes(
        {"unauthorized_retrieval": 0.01, "prompt_injection_success": 0.0}, accepted
    )
    assert not baseline_passes(
        {"unauthorized_retrieval": 0.0, "prompt_injection_success": 1.0}, accepted
    )
    assert not baseline_passes({}, accepted)


def test_guardrail_scenarios_fail_closed_for_injection_and_keep_sensitive_data_local(
    monkeypatch,
):
    dataset_path = Path(__file__).parents[2] / "evals" / "datasets" / "guardrail_scenarios_v1.json"
    cases = json.loads(dataset_path.read_text(encoding="utf-8"))["cases"]
    unsafe = [case for case in cases if case["expected"] == "refuse"]
    private = [case for case in cases if case["expected"] == "local"]
    benign_discount = next(case for case in cases if case["id"] == "business-fact-discount")

    assert len(cases) == 10
    assert all(input_violation(case["prompt"]) for case in unsafe)
    assert all(
        CommerceAssistantService._contains_sensitive_content(case["prompt"]) for case in private
    )
    from src.core.config import settings

    monkeypatch.setattr(settings, "ai_provider", "openrouter")
    assert all(
        CommerceAssistantService._attempted_path(case["prompt"]) == "FAST_PATH" for case in private
    )
    assert not input_violation(benign_discount["prompt"])
