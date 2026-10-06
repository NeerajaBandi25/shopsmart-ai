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

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class ProviderUnavailable(RuntimeError):  # noqa: N818
    """Raised for retryable provider failures."""

    def __init__(
        self, message: str, *, status_code: int | None = None, category: str = "failure"
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.category = category


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
    allow_discovered_free_models: bool = False


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
        selected_external = settings.ai_provider.lower() in {
            "openai_compatible",
            "openrouter",
            "groq",
            "gemini",
        }
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
            "openai_compatible": (settings.openai_api_key, settings.openai_model),
            "openrouter": (settings.openrouter_api_key, settings.openrouter_model),
            "groq": (settings.groq_api_key, settings.groq_model),
            "gemini": (settings.gemini_api_key, settings.gemini_model),
        }
        for provider, (key, model) in configured.items():
            if key:
                priority = 0 if settings.ai_provider.lower() == provider else 50
                policies[provider] = ProviderPolicy(
                    provider,
                    frozenset(
                        {DataClassification.PUBLIC, DataClassification.PRIVATE}
                        if settings.ai_external_private_data_enabled
                        else {DataClassification.PUBLIC}
                    ),
                    frozenset(
                        {item for item in (model, settings.ai_fixed_model) if item}
                        if provider == "openrouter"
                        else {model}
                    ),
                    priority=priority,
                    quota_per_day=1000,
                    retention_policy="provider-policy-required",
                    training_policy="provider-policy-required",
                    allow_discovered_free_models=(
                        provider == "openrouter"
                        and settings.ai_model_routing_mode == "ADAPTIVE_FREE"
                        and model == "openrouter/free"
                    ),
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
        self,
        provider: str,
        model: str,
        classification: DataClassification,
        *,
        discovered_free_model_approved: bool = False,
    ) -> ProviderPolicy:
        policy = self.policies.get(provider)
        if policy is None or not policy.enabled:
            raise PolicyViolation("Provider is not allowlisted")
        model_allowlisted = model in policy.allowed_models
        dynamic_model_allowed = (
            provider == "openrouter"
            and policy.allow_discovered_free_models
            and discovered_free_model_approved
            and classification == DataClassification.PUBLIC
        )
        if not model_allowlisted and not dynamic_model_allowed:
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
