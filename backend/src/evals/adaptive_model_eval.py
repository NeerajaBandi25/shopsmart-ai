"""Controlled, non-mutating OpenRouter free-model comparison and eval-score publisher."""

import argparse
import asyncio
import json
import statistics
import time
from pathlib import Path

from pydantic import ValidationError

from src.core.config import settings
from src.services.adaptive_model_router import AdaptiveFreeModelRouter, ModelRuntimeState
from src.services.ai_gateway import OpenAICompatibleProvider
from src.services.ai_governance import PolicyViolation, ProviderUnavailable
from src.services.assistant_tools import (
    SearchProductsArgs,
    StrictToolArgs,
    UnderstandMissionArgs,
    tool_schemas,
)

DATASET = Path(__file__).parents[2] / "evals" / "datasets" / "adaptive_model_cases_v1.json"
QUALITY_THRESHOLDS = {
    "tool_call_correctness": 1.0,
    "mission_extraction": 1.0,
    "constraint_accuracy": 1.0,
    "grounding": 1.0,
    "recommendation_quality": 1.0,
    "completion_success_rate": 1.0,
}


def quality_gate_failures(metrics: dict[str, float]) -> list[str]:
    """Keep models with any objective failure out of positive routing eval scores."""
    failures = [
        name
        for name, threshold in QUALITY_THRESHOLDS.items()
        if metrics.get(name, -1.0) < threshold
    ]
    for name in ("provider_failures", "rate_limits"):
        if metrics.get(name, 0.0) > 0:
            failures.append(name)
    return failures


def _case_score(
    case: dict,
    tool_ok: bool,
    mission_ok: bool,
    constraints_ok: bool,
    grounded: bool,
    recommended: bool,
) -> float:
    checks = case["score_weights"]
    values = {
        "tool_call_correctness": float(tool_ok),
        "mission_extraction": float(mission_ok),
        "constraint_accuracy": float(constraints_ok),
        "grounding": float(grounded),
        "recommendation_quality": float(recommended),
    }
    active = {key: weight for key, weight in checks.items() if weight > 0}
    denominator = sum(active.values()) or 1.0
    return sum(values[key] * weight for key, weight in active.items()) / denominator


def _completion_success(
    case: dict,
    *,
    tool_ok: bool,
    mission_ok: bool,
    constraints_ok: bool,
    synthesis_ok: bool,
) -> bool:
    required = [tool_ok]
    if case.get("mission_expectations"):
        required.append(mission_ok)
    if case.get("constraint_expectations"):
        required.append(constraints_ok)
    if case.get("tool_result"):
        required.append(synthesis_ok)
    return all(required)


async def run_benchmark(model_ids: list[str] | None = None, *, limit: int = 3) -> dict:
    if not settings.openrouter_api_key:
        raise PolicyViolation("OpenRouter benchmark requires OPENROUTER_API_KEY")
    if limit < 1 or limit > 10:
        raise PolicyViolation("Benchmark limit must be between 1 and 10 models")
    router = AdaptiveFreeModelRouter()
    available = {model.model_id for model in await router._discover()}
    if model_ids is None:
        # Benchmark the best eligible candidates for the primary advice task, not
        # every catalog entry. This keeps live traffic bounded and uses the same
        # eval, health, rate-limit, and latency ranking as production routing.
        selection = await router.select("PRODUCT_ADVICE", streaming_required=False)
        selected = [item for item in selection.candidates if item in available][:limit]
    else:
        selected = sorted(set(model_ids) & available)[:limit]
        if len(set(model_ids)) > limit:
            raise PolicyViolation("Explicit benchmark model set exceeds the configured limit")
    if model_ids and set(model_ids) - available:
        raise PolicyViolation("Every benchmark model must be a discovered free tool-capable model")
    if not selected:
        raise ProviderUnavailable("OpenRouter discovery returned no eligible free tool models")
    cases = json.loads(DATASET.read_text(encoding="utf-8"))["cases"]
    tools = tool_schemas(include_private=False, include_knowledge=False)
    provider = OpenAICompatibleProvider(
        "https://openrouter.ai/api/v1/chat/completions",
        settings.openrouter_api_key,
        "openrouter",
    )
    state = ModelRuntimeState()
    report = {
        "dataset": "adaptive-model-cases-v1",
        "quality_thresholds": QUALITY_THRESHOLDS,
        "models": {},
    }
    for model_id in selected:
        samples = []
        for case in cases:
            started = time.perf_counter()
            sample = {
                "task_type": case["task_type"],
                "expected_tool": case["expected_tool"],
                "called_tools": [],
                "success": False,
                "latency_ms": 0.0,
                "tool_call_correctness": 0.0,
                "mission_extraction": 0.0,
                "constraint_accuracy": 0.0,
                "grounding": 0.0,
                "recommendation_quality": 0.0,
                "input_tokens": 0,
                "output_tokens": 0,
                "request_count": 0,
                "provider_failures": 0,
                "rate_limits": 0,
            }
            try:
                sample["request_count"] += 1
                first = await provider.complete(
                    case["messages"], tools, model_id, timeout_seconds=30
                )
                sample["called_tools"] = [item.name for item in first.tool_calls]
                sample["input_tokens"] += first.input_tokens
                sample["output_tokens"] += first.output_tokens
                call = next(
                    (item for item in first.tool_calls if item.name == case["expected_tool"]),
                    None,
                )
                argument_model = {
                    "search_products": SearchProductsArgs,
                    "understand_shopping_mission": UnderstandMissionArgs,
                    "rank_recommendations": StrictToolArgs,
                }.get(case["expected_tool"])
                parsed_arguments = None
                if call and argument_model:
                    try:
                        parsed_arguments = argument_model.model_validate_json(call.arguments)
                    except ValidationError:
                        parsed_arguments = None
                tool_ok = call is not None and parsed_arguments is not None
                sample["tool_call_correctness"] = float(tool_ok)
                sample["argument_validation_passed"] = parsed_arguments is not None
                constraint_expectations = case.get("constraint_expectations", {})
                if tool_ok and constraint_expectations:
                    sample["constraint_checks"] = {
                        name: {
                            "expected": expected,
                            "actual": getattr(parsed_arguments, name, None),
                            "matched": getattr(parsed_arguments, name, object()) == expected,
                        }
                        for name, expected in constraint_expectations.items()
                    }
                    sample["constraint_accuracy"] = float(
                        all(
                            getattr(parsed_arguments, name, object()) == expected
                            for name, expected in constraint_expectations.items()
                        )
                    )
                else:
                    sample["constraint_accuracy"] = float(tool_ok)
                mission_ok = False
                grounded = False
                recommended = False
                if tool_ok and case.get("mission_expectations"):
                    expected = set(case["mission_expectations"])
                    actual = set(parsed_arguments.desired_use_cases)
                    mission_ok = expected.issubset(actual)
                    sample["mission_missing"] = sorted(expected - actual)
                    sample["mission_extraction"] = float(mission_ok)
                synthesis_ok = True
                if tool_ok and case.get("tool_result"):
                    sample["request_count"] += 1
                    response_turn = await provider.complete(
                        case["messages"]
                        + [
                            {
                                "role": "assistant",
                                "content": first.text or None,
                                "tool_calls": [
                                    {
                                        "id": call.call_id,
                                        "type": "function",
                                        "function": {
                                            "name": call.name,
                                            "arguments": call.arguments,
                                        },
                                    }
                                ],
                            },
                            {
                                "role": "tool",
                                "tool_call_id": call.call_id,
                                "name": call.name,
                                "content": json.dumps(case["tool_result"], separators=(",", ":")),
                            },
                        ],
                        tools,
                        model_id,
                        timeout_seconds=30,
                    )
                    sample["input_tokens"] += response_turn.input_tokens
                    sample["output_tokens"] += response_turn.output_tokens
                    final = response_turn.text.casefold()
                    grounded = all(
                        term.casefold() in final for term in case.get("grounding_terms", [])
                    )
                    recommended = all(
                        term.casefold() in final for term in case.get("recommendation_terms", [])
                    )
                    sample["missing_grounding_terms"] = [
                        term
                        for term in case.get("grounding_terms", [])
                        if term.casefold() not in final
                    ]
                    sample["missing_recommendation_terms"] = [
                        term
                        for term in case.get("recommendation_terms", [])
                        if term.casefold() not in final
                    ]
                    sample["grounding"] = float(grounded)
                    sample["recommendation_quality"] = float(recommended)
                    synthesis_ok = bool(response_turn.text.strip()) and grounded
                    if case.get("recommendation_terms"):
                        synthesis_ok = synthesis_ok and recommended
                sample["success"] = _completion_success(
                    case,
                    tool_ok=tool_ok,
                    mission_ok=mission_ok,
                    constraints_ok=bool(sample["constraint_accuracy"]),
                    synthesis_ok=synthesis_ok,
                )
                sample["eval_score"] = _case_score(
                    case,
                    tool_ok,
                    mission_ok,
                    bool(sample["constraint_accuracy"]),
                    grounded,
                    recommended,
                )
                await state.record(
                    model_id,
                    success=sample["success"],
                    latency_ms=(time.perf_counter() - started) * 1000,
                    status_code=200,
                )
            except ProviderUnavailable as exc:
                sample["error_category"] = exc.category
                sample["status_code"] = exc.status_code
                sample["provider_failures"] += 1
                sample["rate_limits"] += int(exc.status_code == 429)
                await state.record(
                    model_id,
                    success=False,
                    status_code=exc.status_code,
                )
            except PolicyViolation as exc:
                if exc.status_code in {401, 403}:
                    raise
                sample["error_category"] = "model_request_rejected"
                sample["status_code"] = exc.status_code
                sample["provider_failures"] += 1
                sample["rate_limits"] += int(exc.status_code == 429)
                await state.record(
                    model_id,
                    success=False,
                    status_code=exc.status_code,
                )
            sample["latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
            samples.append(sample)
        reliability = sum(item["success"] for item in samples) / len(samples) if samples else 0.0
        latency = statistics.mean(item["latency_ms"] for item in samples) if samples else 0.0
        metric_cases = {
            "tool_call_correctness": list(zip(cases, samples)),
            "mission_extraction": [
                (case, sample)
                for case, sample in zip(cases, samples)
                if case.get("mission_expectations")
            ],
            "constraint_accuracy": [
                (case, sample)
                for case, sample in zip(cases, samples)
                if case.get("constraint_expectations")
            ],
            "grounding": [
                (case, sample)
                for case, sample in zip(cases, samples)
                if case.get("grounding_terms")
            ],
            "recommendation_quality": [
                (case, sample)
                for case, sample in zip(cases, samples)
                if case.get("recommendation_terms")
            ],
        }
        metrics = {
            name: round(sum(sample[name] for _, sample in applicable) / len(applicable), 4)
            if applicable
            else 0.0
            for name, applicable in metric_cases.items()
        }
        metrics["reliability"] = round(reliability, 4)
        metrics["latency_ms_mean"] = round(latency, 2)
        metrics["provider_failures"] = sum(item["provider_failures"] for item in samples)
        metrics["rate_limits"] = sum(item["rate_limits"] for item in samples)
        metrics["request_count"] = sum(item["request_count"] for item in samples)
        metrics["input_tokens"] = sum(item["input_tokens"] for item in samples)
        metrics["output_tokens"] = sum(item["output_tokens"] for item in samples)
        metrics["completion_success_rate"] = round(reliability, 4)
        metrics["eval_score"] = round(
            0.25 * metrics["tool_call_correctness"]
            + 0.15 * metrics["mission_extraction"]
            + 0.15 * metrics["constraint_accuracy"]
            + 0.20 * metrics["grounding"]
            + 0.10 * metrics["recommendation_quality"]
            + 0.10 * reliability
            + 0.05 * (1 - min(latency / 30000, 1)),
            4,
        )
        failed_thresholds = quality_gate_failures(metrics)
        metrics["quality_gate_passed"] = not failed_thresholds
        metrics["quality_gate_failures"] = failed_thresholds
        report["models"][model_id] = {**metrics, "cases": samples}
        for case in cases:
            matching = [item for item in samples if item["task_type"] == case["task_type"]]
            if matching:
                await state.record_eval(
                    model_id,
                    case["task_type"],
                    (
                        sum(item["eval_score"] for item in matching) / len(matching)
                        if not failed_thresholds
                        else 0.0
                    ),
                )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--models",
        help="Optional comma-separated discovered model ids (maximum 3 by default)",
    )
    parser.add_argument("--limit", type=int, default=3, help="Maximum models to compare (1-10)")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    model_ids = (
        [item.strip() for item in args.models.split(",") if item.strip()] if args.models else None
    )
    result = asyncio.run(run_benchmark(model_ids, limit=args.limit))
    encoded = json.dumps(result, indent=2, sort_keys=True)
    print(encoded)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
