"""Deterministic data classification and provider policy enforcement."""

from dataclasses import dataclass, field
from enum import StrEnum
from threading import Lock

from src.core.config import settings


class DataClassification(StrEnum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    PRIVATE = "PRIVATE"
    SENSITIVE = "SENSITIVE"


class PolicyViolation(ValueError):  # noqa: N818
    """Raised when a provider request violates a deterministic policy."""


class ProviderUnavailable(RuntimeError):  # noqa: N818
    """Raised for retryable provider failures."""


@dataclass(frozen=True)
class ProviderPolicy:
    provider: str
    allowed_data_classes: frozenset[DataClassification]
    allowed_models: frozenset[str]
    enabled: bool = True
    priority: int = 100
    quota_per_day: int | None = None
    timeout_seconds: float = 15.0
    retries: int = 1
    fallback_eligible: bool = True
    retention_policy: str = "not-configured"
    training_policy: str = "not-configured"
    health: str = "healthy"


class UsageTracker:
    """Bounded in-process usage counters; prompt content is never retained."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._usage: dict[tuple[str, str], dict[str, int]] = {}

    def can_use(self, provider: str, model: str, policy: ProviderPolicy) -> bool:
        with self._lock:
            if policy.quota_per_day is None:
                return True
            current = self._usage.get((provider, model), {})
            return current.get("requests", 0) < policy.quota_per_day

    def record(
        self,
        provider: str,
        model: str,
        *,
        success: bool,
        status: int | None = None,
        fallback: bool = False,
        tokens: int = 0,
    ) -> None:
        with self._lock:
            item = self._usage.setdefault(
                (provider, model),
                {
                    "requests": 0,
                    "estimated_tokens": 0,
                    "success": 0,
                    "failure": 0,
                    "429": 0,
                    "fallback": 0,
                },
            )
            item["requests"] += 1
            item["estimated_tokens"] += max(tokens, 0)
            item["success" if success else "failure"] += 1
            if status == 429:
                item["429"] += 1
            if fallback:
                item["fallback"] += 1

    def snapshot(self) -> dict[str, dict[str, int]]:
        with self._lock:
            return {
                f"{provider}:{model}": dict(values)
                for (provider, model), values in self._usage.items()
            }


@dataclass
class ProviderPolicyRegistry:
    policies: dict[str, ProviderPolicy] = field(default_factory=dict)

    @classmethod
    def from_settings(cls) -> "ProviderPolicyRegistry":
        selected_external = settings.ai_provider.lower() in {"openrouter", "groq", "gemini"}
        policies = {
            "deterministic": ProviderPolicy(
                "deterministic",
                frozenset(DataClassification),
                frozenset({"local-deterministic-v1"}),
                priority=10 if selected_external else 0,
                quota_per_day=None,
                retention_policy="none",
                training_policy="none",
            ),
        }
        configured = {
            "openrouter": (settings.openrouter_api_key, settings.openrouter_model),
            "groq": (settings.groq_api_key, settings.groq_model),
            "gemini": (settings.gemini_api_key, settings.gemini_model),
        }
        for provider, (key, model) in configured.items():
            if key:
                priority = 0 if settings.ai_provider.lower() == provider else 50
                policies[provider] = ProviderPolicy(
                    provider,
                    frozenset({DataClassification.PUBLIC}),
                    frozenset({model}),
                    priority=priority,
                    quota_per_day=1000,
                    retention_policy="provider-policy-required",
                    training_policy="provider-policy-required",
                )
        return cls(policies)

    def eligible(
        self, classification: DataClassification, usage: UsageTracker
    ) -> list[ProviderPolicy]:
        return sorted(
            (
                policy
                for policy in self.policies.values()
                if policy.enabled
                and policy.health == "healthy"
                and classification in policy.allowed_data_classes
                and any(
                    usage.can_use(policy.provider, model, policy) for model in policy.allowed_models
                )
            ),
            key=lambda policy: policy.priority,
        )

    def validate(
        self, provider: str, model: str, classification: DataClassification
    ) -> ProviderPolicy:
        policy = self.policies.get(provider)
        if policy is None or not policy.enabled:
            raise PolicyViolation("Provider is not allowlisted")
        if model not in policy.allowed_models:
            raise PolicyViolation("Model is not allowlisted")
        if classification not in policy.allowed_data_classes:
            raise PolicyViolation("Provider is not approved for this data classification")
        return policy


def normalize_classification(value: str) -> DataClassification:
    try:
        return DataClassification(value.strip().upper())
    except ValueError as exc:
        raise PolicyViolation("Unsupported data classification") from exc


def highest_classification(values: list[str]) -> DataClassification:
    order = {
        DataClassification.PUBLIC: 0,
        DataClassification.INTERNAL: 1,
        DataClassification.PRIVATE: 2,
        DataClassification.SENSITIVE: 3,
    }
    return max(
        (normalize_classification(value) for value in values),
        key=order.get,
        default=DataClassification.PRIVATE,
    )
