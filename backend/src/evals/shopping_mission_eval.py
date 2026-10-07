"""Programmatic evaluation for the versioned shopping mission and ranking sets."""

import json
from pathlib import Path

from src.services.shopping_mission import extract_shopping_mission

DATASETS = Path(__file__).parents[2] / "evals" / "datasets"


def evaluate_missions(path: Path | None = None) -> dict:
    dataset = json.loads(
        (path or DATASETS / "shopping_missions_v1.json").read_text(encoding="utf-8")
    )
    checks = {
        "category": 0,
        "hard_budget": 0,
        "preferred_budget": 0,
        "workloads": 0,
        "route": 0,
        "clarification": 0,
        "inherited_constraints": 0,
    }
    denominators = checks.copy()
    failures = []
    for case in dataset["scenarios"]:
        previous = extract_shopping_mission(case["previous"]) if case.get("previous") else None
        mission = extract_shopping_mission(case["query"], previous)

        def check(name: str, expected: object, actual: object) -> None:
            if expected is None:
                return
            denominators[name] += 1
            correct = set(actual) >= set(expected) if name == "workloads" else actual == expected
            checks[name] += int(correct)
            if not correct:
                failures.append(
                    {"id": case["id"], "metric": name, "expected": expected, "actual": actual}
                )

        check("category", case.get("category"), mission.category)
        check(
            "hard_budget", case.get("max_budget_cents"), mission.hard_constraints.max_budget_cents
        )
        check(
            "preferred_budget",
            case.get("preferred_budget_cents"),
            mission.soft_constraints.preferred_budget_cents,
        )
        check("workloads", case.get("workloads"), mission.desired_use_cases)
        check("route", case.get("path"), mission.execution_path)
        check("clarification", case.get("clarification"), mission.clarification_needed)
        inherited = case.get("min_ram_gb")
        if inherited is not None:
            denominators["inherited_constraints"] += 1
            ok = mission.hard_constraints.min_ram_gb == inherited
            checks["inherited_constraints"] += int(ok)
            if not ok:
                failures.append(
                    {
                        "id": case["id"],
                        "metric": "inherited_constraints",
                        "expected": inherited,
                        "actual": mission.hard_constraints.min_ram_gb,
                    }
                )
    rates = {
        f"{name}_accuracy": round(checks[name] / denominators[name], 4)
        if denominators[name]
        else 1.0
        for name in checks
    }
    return {
        "dataset": dataset["version"],
        "case_count": len(dataset["scenarios"]),
        "checks": checks,
        "denominators": denominators,
        **rates,
        "failures": failures,
        "passed": not failures,
    }


def main() -> None:
    result = evaluate_missions()
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
