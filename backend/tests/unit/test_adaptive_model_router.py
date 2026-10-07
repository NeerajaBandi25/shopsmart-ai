import httpx
import pytest

from src.core.config import settings
from src.services import adaptive_model_router as router_module
from src.services.adaptive_model_router import (
    AdaptiveFreeModelRouter,
    ModelRuntimeState,
)
from src.services.ai_governance import PolicyViolation


@pytest.mark.asyncio
async def test_adaptive_selection_filters_capabilities_and_ranks_with_eval_and_health(
    monkeypatch,
):
    captured = {}

    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, url, *, headers, params):
            captured.update(url=url, headers=headers, params=params)
            return httpx.Response(
                200,
                request=httpx.Request("GET", url),
                json={
                    "data": [
                        {
                            "id": "zeta/tool-good:free",
                            "pricing": {"prompt": "0", "completion": "0"},
                            "supported_parameters": ["tools", "tool_choice"],
                            "supports_streaming": True,
                        },
                        {
                            "id": "paid/model",
                            "pricing": {"prompt": "0.000001", "completion": "0"},
                            "supported_parameters": ["tools"],
                            "supports_streaming": True,
                        },
                        {
                            "id": "no/tools:free",
                            "pricing": {"prompt": "0", "completion": "0"},
                            "supported_parameters": ["temperature"],
                        },
                        {
                            "id": "alpha/tool-good:free",
                            "pricing": {"prompt": "0", "completion": "0"},
                            "supported_parameters": ["tools"],
                            "supports_streaming": True,
                        },
                    ]
                },
            )

    state = ModelRuntimeState()
    monkeypatch.setattr(router_module.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(router_module, "get_redis_client", lambda: None)
    monkeypatch.setattr(settings, "ai_model_routing_mode", "ADAPTIVE_FREE")
    await state.record_eval("zeta/tool-good:free", "PRODUCT_SEARCH", 0.55)
    await state.record_eval("alpha/tool-good:free", "PRODUCT_SEARCH", 0.95)
    await state.record("alpha/tool-good:free", success=False, status_code=429)
    router = AdaptiveFreeModelRouter(state=state, api_key="test-key")

    selection = await router.select("PRODUCT_SEARCH", streaming_required=True)

    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["params"]["output_modalities"] == "text"
    assert "supported_parameters" not in captured["params"]
    assert selection.selected_model == "zeta/tool-good:free"
    assert selection.candidates[-1] == "openrouter/free"
    assert "paid/model" not in selection.candidates
    assert "no/tools:free" not in selection.candidates
    assert selection.selection_latency_ms >= 0
    factors = {item[0]: item[1:] for item in selection.score_factors}
    assert factors["alpha/tool-good:free"][0] == 0.95
    assert any(reason == "not_free" for _, reason in selection.rejections)
    assert (
        dict(selection.scores)[selection.selected_model]
        > dict(selection.scores)["alpha/tool-good:free"]
    )


@pytest.mark.asyncio
async def test_runtime_state_tracks_failure_latency_429_and_opens_circuit(monkeypatch):
    monkeypatch.setattr(router_module, "get_redis_client", lambda: None)
    state = ModelRuntimeState()
    model = "circuit-test/model:free"
    for _ in range(3):
        await state.record(model, success=False, status_code=429)

    snapshot = await state.snapshot(model, "PRODUCT_SEARCH")

    assert snapshot["health"] == "degraded"
    assert snapshot["429_rate"] == 1.0
    assert snapshot["failure_rate"] == 1.0
    assert snapshot["circuit_state"] == "open"

    with router_module._LOCAL_STATE_LOCK:
        router_module._LOCAL_STATE[(model, "general")]["circuit_expires_at"] = 0
    assert (await state.snapshot(model, "PRODUCT_SEARCH"))["circuit_state"] == "closed"

    await state.record(model, success=True, latency_ms=42.0, status_code=200)
    snapshot = await state.snapshot(model, "PRODUCT_SEARCH")
    assert snapshot["circuit_state"] == "closed"
    assert snapshot["latency"] == 42.0


@pytest.mark.asyncio
async def test_redis_timeout_is_probed_once_per_request_state(monkeypatch):
    class UnavailableRedis:
        def __init__(self):
            self.mget_calls = 0

        async def mget(self, *_keys):
            self.mget_calls += 1
            raise TimeoutError("isolated test Redis is unavailable")

        def pipeline(self, **_kwargs):
            raise AssertionError("writes are skipped after Redis is marked unavailable")

    client = UnavailableRedis()
    monkeypatch.setattr(router_module, "get_redis_client", lambda: client)
    state = ModelRuntimeState()

    first = await state.snapshot("redis-down/first:free", "PRODUCT_ADVICE")
    second = await state.snapshot("redis-down/second:free", "PRODUCT_ADVICE")
    await state.record("redis-down/first:free", success=True, latency_ms=10)

    assert first["health"] == second["health"] == "healthy"
    assert client.mget_calls == 1


@pytest.mark.asyncio
async def test_expired_local_eval_score_returns_neutral_default(monkeypatch):
    monkeypatch.setattr(router_module, "get_redis_client", lambda: None)
    model = "expired-score/model:free"
    state = ModelRuntimeState()
    await state.record_eval(model, "PRODUCT_SEARCH", 0.95)

    with router_module._LOCAL_STATE_LOCK:
        router_module._LOCAL_STATE[(model, "PRODUCT_SEARCH")]["expires_at"] = 0

    snapshot = await state.snapshot(model, "PRODUCT_SEARCH")

    assert snapshot["eval_score"] == 0.5


@pytest.mark.asyncio
async def test_redis_zero_scores_and_rates_override_stale_process_state(monkeypatch):
    class RedisSnapshot:
        async def mget(self, *_keys):
            return ["healthy", 0, 0, 0, "closed", 0]

    model = "redis-zero/authoritative:free"
    state = ModelRuntimeState()
    await state.record_eval(model, "PRODUCT_SEARCH", 0.8)
    await state.record(model, success=False, status_code=429)
    monkeypatch.setattr(router_module, "get_redis_client", lambda: RedisSnapshot())

    snapshot = await state.snapshot(model, "PRODUCT_SEARCH")

    assert snapshot["health"] == "healthy"
    assert snapshot["latency"] == 0
    assert snapshot["429_rate"] == 0
    assert snapshot["failure_rate"] == 0
    assert snapshot["circuit_state"] == "closed"
    assert snapshot["eval_score"] == 0


@pytest.mark.asyncio
async def test_failed_eval_quality_gate_rejects_model_from_adaptive_candidates(monkeypatch):
    monkeypatch.setattr(router_module, "get_redis_client", lambda: None)
    monkeypatch.setattr(settings, "ai_model_routing_mode", "ADAPTIVE_FREE")
    state = ModelRuntimeState()
    await state.record_eval("failed/model:free", "PRODUCT_ADVICE", 0)
    router = AdaptiveFreeModelRouter(state=state)
    router._catalog = (
        router_module.ModelCandidate("failed/model:free", frozenset({"tools"})),
        router_module.ModelCandidate("eligible/model:free", frozenset({"tools"})),
    )
    router._catalog_expires_at = 9999999999

    selection = await router.select("PRODUCT_ADVICE", streaming_required=False)

    assert selection.selected_model == "eligible/model:free"
    assert "failed/model:free" not in selection.candidates
    assert ("failed/model:free", "eval_quality_gate_failed") in selection.rejections


@pytest.mark.asyncio
async def test_fixed_requires_concrete_model_and_benchmark_is_eval_only(monkeypatch):
    monkeypatch.setattr(settings, "ai_model_routing_mode", "FIXED")
    monkeypatch.setattr(settings, "ai_fixed_model", "openrouter/free")
    router = AdaptiveFreeModelRouter()
    with pytest.raises(PolicyViolation, match="explicit concrete"):
        await router.select("PRODUCT_SEARCH", streaming_required=False)

    monkeypatch.setattr(settings, "ai_model_routing_mode", "BENCHMARK")
    with pytest.raises(PolicyViolation, match="controlled eval runner"):
        await router.select("PRODUCT_SEARCH", streaming_required=False)


@pytest.mark.asyncio
async def test_streaming_selection_accepts_unknown_and_rejects_explicitly_unsupported(monkeypatch):
    monkeypatch.setattr(router_module, "get_redis_client", lambda: None)
    router = AdaptiveFreeModelRouter(api_key="test-key")
    router._catalog = (
        router_module.ModelCandidate("unknown/stream:free", frozenset({"tools"}), None),
        router_module.ModelCandidate("no-stream/model:free", frozenset({"tools"}), False),
    )
    router._catalog_expires_at = 9999999999

    selection = await router.select("PRODUCT_SEARCH", streaming_required=True)

    assert selection.candidates == ("unknown/stream:free", "openrouter/free")
    assert ("no-stream/model:free", "streaming_explicitly_unsupported") in selection.rejections


@pytest.mark.asyncio
async def test_model_discovery_auth_failure_is_not_hidden_by_emergency_alias(monkeypatch):
    class UnauthorizedClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, url, **_kwargs):
            return httpx.Response(401, request=httpx.Request("GET", url))

    monkeypatch.setattr(router_module.httpx, "AsyncClient", UnauthorizedClient)
    monkeypatch.setattr(router_module, "get_redis_client", lambda: None)
    router = AdaptiveFreeModelRouter(api_key="test-key")

    with pytest.raises(PolicyViolation) as error:
        await router.select("PRODUCT_SEARCH", streaming_required=False)
    assert error.value.status_code == 401
