"""Response schemas for operator-facing observability data."""

from pydantic import BaseModel, Field


class RequestDurationMetric(BaseModel):
    count: int
    total: float
    max: float


class MetricsSnapshot(BaseModel):
    requests: dict[str, int]
    request_duration_ms: dict[str, RequestDurationMetric]
    security_events: dict[str, int]
    ai_events: dict[str, int] = Field(default_factory=dict)
