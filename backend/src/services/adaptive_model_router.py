"""Request-level OpenRouter free-model discovery, scoring, pinning, and health state."""

import json
import logging
import re
import time
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from threading import Lock
from uuid import uuid4

import httpx
from redis.exceptions import RedisError

from src.core.config import settings
from src.core.redis_client import get_redis_client
from src.services.ai_governance import PolicyViolation, ProviderUnavailable

logger = logging.getLogger("shopsmart.ai_gateway")

MODEL_CATALOG_TTL = 180
MODEL_HEALTH_TTL = 300
MODEL_LATENCY_TTL = 3600
MODEL_RATE_TTL = 900
MODEL_CIRCUIT_TTL = 60
FREE_ROUTER_MODEL = "openrouter/free"
MAX_RANKED_MODELS = 4
_LOCAL_STATE_LOCK = Lock()
_LOCAL_STATE: dict[tuple[str, str], dict] = {}


@dataclass(frozen=True)
class ModelCandidate:
    model_id: str
    supported_parameters: frozenset[str]
    supports_streaming: bool | None = None


@dataclass(frozen=True)
class ModelSelection:
    mode: str
    task_type: str
    streaming_required: bool
    candidates: tuple[str, ...]
    scores: tuple[tuple[str, float], ...]
    rejections: tuple[tuple[str, str], ...] = ()
    score_factors: tuple[tuple[str, float, float, float, float, float], ...] = ()
    selection_latency_ms: float = 0.0

    @property
    def selected_model(self) -> str:
        return self.candidates[0]


class ModelRuntimeState:
    """Short-lived model health, latency, reliability, 429, and circuit metrics."""

    def __init__(self) -> None:
        # Probe Redis once per request-scoped state object. A Redis outage must not
        # add one socket timeout for every free-model candidate and tool round.
        self._redis_unavailable = False

    async def snapshot(self, model_id: str, task_type: str) -> dict[str, float | str]:
        key = self._key(model_id)
        client = get_redis_client()
        if client and not self._redis_unavailable:
            try:
                values = await client.mget(
                    key + ":health",
                    key + ":latency",
                    key + ":429_rate",
                    key + ":failure_rate",
                    key + ":circuit_state",
                    key + ":eval_score:" + self._task(task_type),
                )
                result = self._local_snapshot(model_id, task_type)
                result.update(
                    {
                        "health": values[0] if values[0] is not None else result["health"],
                        "latency": (
                            float(values[1]) if values[1] is not None else result["latency"]
                        ),
                        "429_rate": (
                            float(values[2]) if values[2] is not None else result["429_rate"]
                        ),
                        "failure_rate": (
                            float(values[3]) if values[3] is not None else result["failure_rate"]
                        ),
                        "circuit_state": (
                            values[4] if values[4] is not None else result["circuit_state"]
                        ),
                        "eval_score": (
                            float(values[5]) if values[5] is not None else result["eval_score"]
                        ),
                    }
                )
                return result
            except (RedisError, TimeoutError, TypeError, ValueError) as exc:
                self._redis_unavailable = True
                logger.warning(
                    "adaptive_model_state_degraded",
                    extra={
                        "event": "adaptive_model_state_degraded",
                        "model": model_id,
                        "exception_type": type(exc).__name__,
                    },
                )
        return self._local_snapshot(model_id, task_type)

    async def record(
        self,
        model_id: str,
        *,
        success: bool,
        latency_ms: float | None = None,
        status_code: int | None = None,
    ) -> None:
        key = self._key(model_id)
        now = time.monotonic()
        with _LOCAL_STATE_LOCK:
            item = _LOCAL_STATE.setdefault(
                (model_id, "general"),
                {"events": [], "streak": 0},
            )
            events = item.setdefault("events", [])
            events[:] = [event for event in events if now - event[0] < MODEL_RATE_TTL]
            events.append((now, not success, status_code == 429))
            item["requests"] = len(events)
            item["failures"] = sum(event[1] for event in events)
            item["rate_limits"] = sum(event[2] for event in events)
            item["streak"] = 0 if success else item["streak"] + 1
            item.update(
                {
                    "health": "healthy" if success else "degraded",
                    "latency": latency_ms
                    if success and latency_ms is not None
                    else item.get("latency", 15000.0),
                    "429_rate": item["rate_limits"] / max(item["requests"], 1),
                    "failure_rate": item["failures"] / max(item["requests"], 1),
                    "circuit_state": "open"
                    if item["streak"] >= 3
                    else ("closed" if success else "half_open"),
                    "eval_score": item.get("eval_score", 0.5),
                    "expires_at": now + MODEL_RATE_TTL,
                    "circuit_expires_at": now + MODEL_CIRCUIT_TTL,
                }
            )
        client = get_redis_client()
        if not client or self._redis_unavailable:
            return
        try:
            window_key = key + ":window"
            now_epoch = time.time()
            member = f"{int(not success)}:{int(status_code == 429)}:{uuid4().hex}"
            pipe = client.pipeline(transaction=True)
            pipe.zremrangebyscore(window_key, "-inf", now_epoch - MODEL_RATE_TTL)
            pipe.zadd(window_key, {member: now_epoch})
            pipe.zremrangebyrank(window_key, 0, -501)
            pipe.expire(window_key, MODEL_RATE_TTL)
            streak_key = key + ":consecutive_failures"
            if success:
                pipe.set(streak_key, 0, ex=MODEL_RATE_TTL)
            else:
                pipe.incr(streak_key)
                pipe.expire(streak_key, MODEL_RATE_TTL)
            await pipe.execute()
            events = await client.zrange(window_key, 0, -1)
            requests = max(len(events), 1)
            failures = sum(event.startswith("1:") for event in events)
            limits = sum(event.startswith(("0:1:", "1:1:")) for event in events)
            streak = max(int(await client.get(streak_key) or 0), 0)
            circuit = "open" if streak >= 3 else ("closed" if success else "half_open")
            pipe = client.pipeline(transaction=True)
            pipe.set(key + ":health", "healthy" if success else "degraded", ex=MODEL_HEALTH_TTL)
            pipe.set(key + ":429_rate", limits / requests, ex=MODEL_RATE_TTL)
            pipe.set(key + ":failure_rate", failures / requests, ex=MODEL_RATE_TTL)
            pipe.set(key + ":circuit_state", circuit, ex=MODEL_CIRCUIT_TTL)
            if latency_ms is not None and success:
                pipe.set(key + ":latency", max(0.0, latency_ms), ex=MODEL_LATENCY_TTL)
            await pipe.execute()
        except (RedisError, TimeoutError):
            self._redis_unavailable = True
            logger.warning(
                "adaptive_model_state_degraded",
                extra={"event": "adaptive_model_state_degraded", "model": model_id},
            )

    async def record_eval(self, model_id: str, task_type: str, score: float) -> None:
        normalized_score = min(1.0, max(0.0, score))
        with _LOCAL_STATE_LOCK:
            item = _LOCAL_STATE.setdefault((model_id, task_type), {})
            item.update(eval_score=normalized_score, expires_at=time.monotonic() + 86400)
        client = get_redis_client()
        if not client or self._redis_unavailable:
            return
        try:
            await client.set(
                self._key(model_id) + ":eval_score:" + self._task(task_type),
                normalized_score,
                ex=86400,
            )
        except (RedisError, TimeoutError):
            self._redis_unavailable = True
            logger.warning(
                "adaptive_model_eval_state_degraded",
                extra={"event": "adaptive_model_eval_state_degraded", "model": model_id},
            )

    @staticmethod
    def _defaults() -> dict[str, float | str]:
        return {
            "health": "healthy",
            "latency": 15000.0,
            "429_rate": 0.0,
            "failure_rate": 0.0,
            "circuit_state": "closed",
            "eval_score": 0.5,
        }

    @classmethod
    def _local_snapshot(cls, model_id: str, task_type: str) -> dict[str, float | str]:
        result = cls._defaults()
        now = time.monotonic()
        with _LOCAL_STATE_LOCK:
            for key in ((model_id, "general"), (model_id, task_type)):
                item = _LOCAL_STATE.get(key, {})
                if item.get("expires_at", 0) > now:
                    result.update(
                        {
                            name: value
                            for name, value in item.items()
                            if name not in {"expires_at", "circuit_expires_at", "events"}
                        }
                    )
                    if item.get("circuit_expires_at", 0) <= now:
                        result["circuit_state"] = "closed"
        return result

    @staticmethod
    def _task(task_type: str) -> str:
        normalized = "".join(char.lower() if char.isalnum() else "_" for char in task_type)
        return normalized.strip("_")[:40] or "general"

    @staticmethod
    def _key(model_id: str) -> str:
        return "ai:model:" + model_id


class AdaptiveFreeModelRouter:
    """Discovers free tool-capable models and ranks them without random rotation."""

    def __init__(
        self,
        *,
        state: ModelRuntimeState | None = None,
        api_key: str | None = None,
        catalog_endpoint: str = "https://openrouter.ai/api/v1/models",
    ) -> None:
        self.state = state or ModelRuntimeState()
        self.api_key = api_key if api_key is not None else settings.openrouter_api_key
        self.catalog_endpoint = catalog_endpoint
        self._catalog: tuple[ModelCandidate, ...] = ()
        self._catalog_rejections: tuple[tuple[str, str], ...] = ()
        self._catalog_expires_at = 0.0

    async def select(self, task_type: str, *, streaming_required: bool) -> ModelSelection:
        started = time.perf_counter()
        mode = settings.ai_model_routing_mode
        if mode == "FIXED":
            model = settings.ai_fixed_model or ""
            if not model or model == FREE_ROUTER_MODEL:
                raise PolicyViolation("FIXED routing requires an explicit concrete AI_FIXED_MODEL")
            return ModelSelection(mode, task_type, streaming_required, (model,), ((model, 1.0),))
        if mode == "BENCHMARK":
            raise PolicyViolation("BENCHMARK routing is reserved for the controlled eval runner")

        try:
            models = await self._discover()
            rejections = list(self._catalog_rejections)
        except ProviderUnavailable as exc:
            models = ()
            rejections = [("model-catalog", f"discovery_{exc.category}")]
        scored = []
        factors = []
        for candidate in models:
            # OpenRouter's public model catalog does not publish a stable
            # per-model streaming flag. Its chat-completions API accepts stream
            # requests; the provider adapter falls back to buffered completion
            # for the same pinned model if an upstream endpoint rejects SSE.
            if streaming_required and candidate.supports_streaming is False:
                rejections.append((candidate.model_id, "streaming_explicitly_unsupported"))
                continue
            state = await self.state.snapshot(candidate.model_id, task_type)
            if state["circuit_state"] == "open" or state["health"] == "unhealthy":
                rejections.append((candidate.model_id, "circuit_open_or_unhealthy"))
                continue
            eval_score = float(state["eval_score"])
            if eval_score <= 0:
                rejections.append((candidate.model_id, "eval_quality_gate_failed"))
                continue
            reliability = 1.0 - float(state["failure_rate"])
            rate_limit_score = 1.0 - float(state["429_rate"])
            latency_score = 1.0 - min(float(state["latency"]) / 15000.0, 1.0)
            score = (
                0.50 * eval_score
                + 0.25 * reliability
                + 0.15 * rate_limit_score
                + 0.10 * latency_score
            )
            scored.append((candidate.model_id, score))
            factors.append(
                (
                    candidate.model_id,
                    eval_score,
                    reliability,
                    rate_limit_score,
                    latency_score,
                    score,
                )
            )
        scored.sort(key=lambda item: (-item[1], item[0]))
        scored = scored[:MAX_RANKED_MODELS]
        ranked = [item[0] for item in scored]
        if FREE_ROUTER_MODEL not in ranked:
            ranked.append(FREE_ROUTER_MODEL)
            scored.append((FREE_ROUTER_MODEL, 0.0))
        selection = ModelSelection(
            mode,
            task_type,
            streaming_required,
            tuple(ranked),
            tuple(scored),
            tuple(rejections[:50]),
            tuple(factors),
            round((time.perf_counter() - started) * 1000, 2),
        )
        logger.info(
            "AI_MODEL_SELECTED",
            extra={
                "event": "AI_MODEL_SELECTED",
                "provider": "openrouter",
                "model": selection.selected_model,
                "routing_mode": mode,
                "task_type": task_type,
                "candidate_count": len(ranked),
                "eligible_models": ranked[:MAX_RANKED_MODELS],
                "rejected_models": [
                    {"model": model, "reason": reason} for model, reason in selection.rejections
                ],
                "score_factors": [
                    {
                        "model": model,
                        "eval": eval_score,
                        "reliability": reliability,
                        "429_avoidance": no_429,
                        "latency": latency,
                        "total": total,
                    }
                    for model, eval_score, reliability, no_429, latency, total in factors
                ],
                "streaming_required": streaming_required,
                "selection_latency_ms": selection.selection_latency_ms,
            },
        )
        return selection

    async def _discover(self) -> tuple[ModelCandidate, ...]:
        now = time.monotonic()
        if self._catalog and now < self._catalog_expires_at:
            return self._catalog
        redis_client = get_redis_client()
        if redis_client:
            try:
                cached = await redis_client.get("ai:model:catalog:openrouter:free")
                if cached:
                    self._catalog, self._catalog_rejections = self._parse_catalog(
                        json.loads(cached)
                    )
                    self._catalog_expires_at = now + MODEL_CATALOG_TTL
                    return self._catalog
            except (RedisError, ValueError, TypeError):
                pass
        if not self.api_key:
            raise ProviderUnavailable("OpenRouter model discovery is not configured")
        try:
            async with httpx.AsyncClient(timeout=10) as http_client:
                response = await http_client.get(
                    self.catalog_endpoint,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    params={"output_modalities": "text"},
                )
        except httpx.TimeoutException as exc:
            raise ProviderUnavailable("OpenRouter model discovery timed out") from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailable("OpenRouter model discovery connection failed") from exc
        if response.status_code in {401, 403}:
            raise PolicyViolation(
                f"OpenRouter model discovery rejected credentials: {response.status_code}",
                status_code=response.status_code,
            )
        if response.status_code == 429 or response.status_code >= 500:
            raise ProviderUnavailable(f"OpenRouter model discovery failed: {response.status_code}")
        if response.status_code >= 400:
            raise PolicyViolation(
                f"OpenRouter model discovery rejected request: {response.status_code}"
            )
        payload = response.json()
        self._catalog, self._catalog_rejections = self._parse_catalog(payload.get("data", []))
        self._catalog_expires_at = now + MODEL_CATALOG_TTL
        if redis_client:
            try:
                await redis_client.set(
                    "ai:model:catalog:openrouter:free",
                    json.dumps(payload.get("data", []), separators=(",", ":")),
                    ex=MODEL_CATALOG_TTL,
                )
            except RedisError:
                pass
        return self._catalog

    @staticmethod
    def _parse_catalog(
        items: list[dict],
    ) -> tuple[tuple[ModelCandidate, ...], tuple[tuple[str, str], ...]]:
        models = []
        rejected = []
        for item in items:
            model_id = item.get("id")
            pricing = item.get("pricing") or {}
            if (
                not isinstance(model_id, str)
                or not re.fullmatch(r"[A-Za-z0-9._:/-]{1,160}", model_id)
                or model_id == FREE_ROUTER_MODEL
            ):
                if isinstance(model_id, str) and len(model_id) <= 160:
                    rejected.append((model_id, "invalid_or_router_alias"))
                continue
            try:
                prompt = Decimal(str(pricing.get("prompt", "-1")))
                completion = Decimal(str(pricing.get("completion", "-1")))
            except (InvalidOperation, ValueError):
                rejected.append((model_id, "invalid_pricing_metadata"))
                continue
            if prompt != 0 or completion != 0:
                rejected.append((model_id, "not_free"))
                continue
            supported = frozenset(item.get("supported_parameters") or [])
            if "tools" not in supported:
                rejected.append((model_id, "tool_calling_not_supported"))
                continue
            models.append(
                ModelCandidate(
                    model_id=model_id,
                    supported_parameters=supported,
                    supports_streaming=(
                        item.get("supports_streaming")
                        if isinstance(item.get("supports_streaming"), bool)
                        else None
                    ),
                )
            )
        return (
            tuple(sorted(models, key=lambda item: item.model_id)),
            tuple(rejected[:50]),
        )
