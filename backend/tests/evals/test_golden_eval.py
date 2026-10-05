from pathlib import Path

from src.evals.runner import aggregate, load_dataset, score_case

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
