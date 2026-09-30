"""Deterministic provider-routing evaluation cases."""

from dataclasses import dataclass

from src.services.ai_governance import (
    DataClassification,
    ProviderPolicy,
    ProviderPolicyRegistry,
    UsageTracker,
)


@dataclass(frozen=True)
class RoutingEvalCase:
    name: str
    classification: DataClassification
    expected_providers: tuple[str, ...]


ROUTING_CASES = (
    RoutingEvalCase("public-allows-deterministic", DataClassification.PUBLIC, ("deterministic",)),
    RoutingEvalCase("private-local-only", DataClassification.PRIVATE, ("deterministic",)),
    RoutingEvalCase("sensitive-local-only", DataClassification.SENSITIVE, ("deterministic",)),
)


def evaluate_routing() -> dict[str, float]:
    registry = ProviderPolicyRegistry(
        {
            "deterministic": ProviderPolicy(
                "deterministic",
                frozenset(DataClassification),
                frozenset({"local-deterministic-v1"}),
                priority=0,
            ),
            "public-external": ProviderPolicy(
                "public-external",
                frozenset({DataClassification.PUBLIC}),
                frozenset({"pinned-v1"}),
                priority=10,
            ),
        }
    )
    usage = UsageTracker()
    passed = 0
    for case in ROUTING_CASES:
        actual = tuple(policy.provider for policy in registry.eligible(case.classification, usage))
        if actual == case.expected_providers or (
            case.classification is DataClassification.PUBLIC
            and actual == ("deterministic", "public-external")
        ):
            passed += 1
    return {
        "case_count": float(len(ROUTING_CASES)),
        "passed": float(passed),
        "pass_rate": passed / len(ROUTING_CASES),
    }
