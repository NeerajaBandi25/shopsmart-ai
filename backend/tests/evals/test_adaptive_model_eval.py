import json
from pathlib import Path

from src.evals.adaptive_model_eval import (
    DATASET,
    QUALITY_THRESHOLDS,
    _case_score,
    _completion_success,
    _ensure_case_score,
    _mission_expectation_result,
    quality_gate_failures,
    task_quality_gate_failures,
)


def test_adaptive_model_eval_dataset_scores_tool_mission_grounding_and_recommendations():
    dataset = json.loads(Path(DATASET).read_text(encoding="utf-8"))
    assert dataset["version"] == "adaptive-model-cases-v2"
    assert {item["task_type"] for item in dataset["cases"]} == {
        "PRODUCT_SEARCH",
        "PRODUCT_ADVICE",
        "PRODUCT_COMPARE",
    }
    assert len(dataset["cases"]) == 6
    mission_case = next(item for item in dataset["cases"] if item.get("mission_expectations"))

    perfect = _case_score(mission_case, True, True, True, False, False)
    missed_mission = _case_score(mission_case, True, False, True, False, False)

    assert perfect == 1.0
    assert missed_mission == 0.35 / (0.35 + 0.65)
    constrained_case = next(
        item for item in dataset["cases"] if item.get("constraint_expectations")
    )
    assert _case_score(constrained_case, True, True, False, True, False) < _case_score(
        constrained_case, True, True, True, True, False
    )
    assert not _completion_success(
        mission_case,
        tool_ok=True,
        mission_ok=False,
        constraints_ok=True,
        synthesis_ok=True,
    )
    search_case = next(item for item in dataset["cases"] if item.get("constraint_expectations"))
    assert not _completion_success(
        search_case,
        tool_ok=True,
        mission_ok=True,
        constraints_ok=False,
        synthesis_ok=True,
    )


def test_mission_eval_checks_soft_preference_fields_as_well_as_use_cases():
    case = {
        "mission_expectations": ["student"],
        "mission_field_expectations": {"portability": True},
    }
    from src.services.assistant_tools import UnderstandMissionArgs

    complete = UnderstandMissionArgs(desired_use_cases=["student"], portability=True)
    missing_soft_preference = UnderstandMissionArgs(desired_use_cases=["student"])

    assert _mission_expectation_result(case, complete)[0]
    assert not _mission_expectation_result(case, missing_soft_preference)[0]


def test_adaptive_model_quality_gate_requires_perfect_objective_cases_and_reliability():
    metrics = {name: value for name, value in QUALITY_THRESHOLDS.items()}
    metrics.update(provider_failures=0.0, rate_limits=0.0)
    assert quality_gate_failures(metrics) == []

    metrics["tool_call_correctness"] = 0.9
    metrics["provider_failures"] = 1.0
    assert set(quality_gate_failures(metrics)) == {"tool_call_correctness", "provider_failures"}


def test_provider_failure_case_keeps_zero_score_for_complete_benchmark_report():
    case = {
        "score_weights": {"tool_call_correctness": 0.5, "grounding": 0.5},
    }
    sample = {"error_category": "provider_unavailable"}

    _ensure_case_score(case, sample)

    assert sample["eval_score"] == 0.0


def test_task_quality_gate_only_uses_objective_checks_for_that_task():
    search_case = {
        "task_type": "PRODUCT_SEARCH",
        "score_weights": {"tool_call_correctness": 0.35, "constraint_accuracy": 0.65},
    }
    advice_case = {
        "task_type": "PRODUCT_ADVICE",
        "score_weights": {"tool_call_correctness": 0.35, "mission_extraction": 0.65},
    }
    search_sample = {
        "tool_call_correctness": 1.0,
        "constraint_accuracy": 1.0,
        "mission_extraction": 0.0,
        "success": True,
        "provider_failures": 0,
        "rate_limits": 0,
    }
    advice_sample = {
        "tool_call_correctness": 1.0,
        "constraint_accuracy": 1.0,
        "mission_extraction": 0.0,
        "success": False,
        "provider_failures": 0,
        "rate_limits": 0,
    }

    assert task_quality_gate_failures([search_case], [search_sample]) == []
    assert set(task_quality_gate_failures([advice_case], [advice_sample])) == {
        "mission_extraction",
        "completion_success_rate",
    }
