"""Provider-native tool-call normalization tests use mocked HTTP, never real credentials."""

import json

import httpx
import pytest

from src.services.adaptive_model_router import ModelSelection
from src.services.ai_gateway import (
    GeminiProvider,
    OpenAICompatibleProvider,
    ProviderGateway,
    ProviderUnavailable,
    StreamingUnsupported,
    ToolTurn,
)
from src.services.ai_governance import (
    DataClassification,
    PolicyViolation,
    ProviderPolicy,
    ProviderPolicyRegistry,
    UsageTracker,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [400, 422, 401, 403])
async def test_openai_compatible_provider_preserves_http_rejection_status(monkeypatch, status_code):
    class RejectedClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, url, **_kwargs):
            return httpx.Response(status_code, request=httpx.Request("POST", url))

    monkeypatch.setattr("src.services.ai_gateway.httpx.AsyncClient", RejectedClient)
    provider = OpenAICompatibleProvider("https://provider.test/v1/chat/completions", "key", "test")

    with pytest.raises(PolicyViolation) as rejected:
        await provider.complete([], [], "candidate/model:free", 1)

    assert rejected.value.status_code == status_code


@pytest.mark.asyncio
async def test_openai_compatible_provider_sends_tools_and_normalizes_function_call(monkeypatch):
    captured = {}

    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, url, *, headers, json):
            captured.update(url=url, headers=headers, payload=json)
            return httpx.Response(
                200,
                request=httpx.Request("POST", url),
                json={
                    "choices": [
                        {
                            "message": {
                                "content": None,
                                "tool_calls": [
                                    {
                                        "id": "call-1",
                                        "function": {
                                            "name": "search_products",
                                            "arguments": '{"category":"laptops"}',
                                        },
                                    }
                                ],
                            }
                        }
                    ],
                    "model": "provider/selected-free-model",
                    "usage": {"prompt_tokens": 12, "completion_tokens": 4},
                },
            )

    monkeypatch.setattr("src.services.ai_gateway.httpx.AsyncClient", FakeClient)
    provider = OpenAICompatibleProvider(
        "https://provider.test/v1/chat/completions", "secret", "test"
    )
    tools = [{"type": "function", "function": {"name": "search_products"}}]
    turn = await provider.complete(
        [{"role": "user", "content": "Find laptops"}], tools, "test-model", 2
    )

    assert captured["url"] == "https://provider.test/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer secret"
    assert captured["payload"]["tools"] == tools
    assert turn.tool_calls[0].name == "search_products"
    assert json.loads(turn.tool_calls[0].arguments) == {"category": "laptops"}
    assert (turn.input_tokens, turn.output_tokens) == (12, 4)
    assert turn.reported_model == "provider/selected-free-model"


@pytest.mark.asyncio
async def test_openai_compatible_stream_reassembles_partial_tool_arguments(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def aiter_lines(self):
            for item in (
                {
                    "model": "provider/selected-stream-model",
                    "choices": [
                        {
                            "delta": {
                                "tool_calls": [
                                    {
                                        "index": 0,
                                        "id": "call-1",
                                        "function": {
                                            "name": "search_products",
                                            "arguments": '{"category":',
                                        },
                                    }
                                ]
                            }
                        }
                    ],
                },
                {
                    "choices": [
                        {
                            "delta": {
                                "tool_calls": [
                                    {"index": 0, "function": {"arguments": '"laptops"}'}}
                                ]
                            }
                        }
                    ]
                },
                {"choices": [], "usage": {"prompt_tokens": 9, "completion_tokens": 2}},
            ):
                yield "data: " + json.dumps(item)
            yield "data: [DONE]"

    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        def stream(self, method, url, *, headers, json):
            captured.update(method=method, url=url, headers=headers, payload=json)
            return FakeResponse()

    monkeypatch.setattr("src.services.ai_gateway.httpx.AsyncClient", FakeClient)
    provider = OpenAICompatibleProvider("https://provider.test/chat/completions", "secret", "test")
    turn = await provider.complete_stream([], [], "test-model", 2)

    assert captured["payload"]["stream"] is True
    assert captured["headers"]["Accept"] == "text/event-stream"
    assert turn.tool_calls[0].name == "search_products"
    assert json.loads(turn.tool_calls[0].arguments) == {"category": "laptops"}
    assert (turn.input_tokens, turn.output_tokens) == (9, 2)
    assert turn.reported_model == "provider/selected-stream-model"


@pytest.mark.asyncio
async def test_gateway_falls_back_to_buffered_call_when_provider_rejects_streaming():
    class StreamLimitedProvider:
        async def complete_stream(self, *_args):
            raise StreamingUnsupported("stream unsupported")

        async def complete(self, *_args):
            return ToolTurn("", (), 4, 2)

    policy = ProviderPolicy(
        provider="openai_compatible",
        allowed_data_classes=frozenset({DataClassification.PUBLIC}),
        allowed_models=frozenset({"model"}),
        retries=0,
    )
    gateway = ProviderGateway(
        registry=ProviderPolicyRegistry({policy.provider: policy}),
        providers={policy.provider: StreamLimitedProvider()},
        usage=UsageTracker(),
    )

    turn, provider, model = await gateway.tool_turn(
        [], [], DataClassification.PUBLIC, streaming=True
    )

    assert (provider, model) == ("openai_compatible", "model")
    assert (turn.input_tokens, turn.output_tokens) == (4, 2)


@pytest.mark.asyncio
async def test_provider_rate_limit_is_retryable_before_any_tool_is_executed(monkeypatch):
    captured_logs = []
    monkeypatch.setattr(
        "src.services.ai_gateway.logger.warning",
        lambda message, **context: captured_logs.append((message, context)),
    )

    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, url, **_kwargs):
            return httpx.Response(429, request=httpx.Request("POST", url))

    monkeypatch.setattr("src.services.ai_gateway.httpx.AsyncClient", FakeClient)
    provider = OpenAICompatibleProvider("https://provider.test/chat/completions", "secret", "test")
    with pytest.raises(ProviderUnavailable):
        await provider.complete([], [], "test-model", 2)
    message, failure = captured_logs[-1]
    assert message == "provider_request_failed"
    assert failure["extra"]["provider_error_category"] == "rate_limited"
    assert failure["extra"]["provider_http_status"] == 429
    assert "secret" not in str(failure)


@pytest.mark.asyncio
async def test_gateway_uses_explicit_request_pinned_model():
    selected = []

    class FixedModelProvider:
        async def complete(self, _messages, _tools, model, _timeout):
            selected.append(model)
            return ToolTurn("done", (), 3, 2, model)

    class State:
        async def record(self, *_args, **_kwargs):
            return None

    policy = ProviderPolicy(
        provider="openrouter",
        allowed_data_classes=frozenset({DataClassification.PUBLIC}),
        allowed_models=frozenset({"openrouter/free"}),
        retries=0,
        allow_discovered_free_models=True,
    )
    gateway = ProviderGateway(
        registry=ProviderPolicyRegistry({"openrouter": policy}),
        providers={"openrouter": FixedModelProvider()},
        usage=UsageTracker(),
        model_router=type("Router", (), {"state": State()})(),
    )

    turn, provider, model = await gateway.tool_turn(
        [],
        [],
        DataClassification.PUBLIC,
        model_override="poolside/laguna-s-2.1:free",
        model_selection=ModelSelection(
            "ADAPTIVE_FREE",
            "PRODUCT_SEARCH",
            False,
            ("poolside/laguna-s-2.1:free", "openrouter/free"),
            (),
        ),
    )

    assert selected == ["poolside/laguna-s-2.1:free"]
    assert (provider, model, turn.reported_model) == (
        "openrouter",
        "poolside/laguna-s-2.1:free",
        "poolside/laguna-s-2.1:free",
    )


@pytest.mark.asyncio
async def test_gateway_rejects_unresolved_free_alias_before_agent_can_continue():
    class AliasProvider:
        async def complete(self, _messages, _tools, _model, _timeout):
            return ToolTurn("done", (), 3, 2, None)

    class State:
        def __init__(self):
            self.failures = []

        async def record(self, model, **kwargs):
            self.failures.append((model, kwargs))

    state = State()
    policy = ProviderPolicy(
        provider="openrouter",
        allowed_data_classes=frozenset({DataClassification.PUBLIC}),
        allowed_models=frozenset({"openrouter/free"}),
        retries=0,
    )
    gateway = ProviderGateway(
        registry=ProviderPolicyRegistry({"openrouter": policy}),
        providers={"openrouter": AliasProvider()},
        usage=UsageTracker(),
        model_router=type("Router", (), {"state": state})(),
    )

    with pytest.raises(ProviderUnavailable, match="did not report a concrete model id"):
        await gateway.tool_turn([], [], DataClassification.PUBLIC, model_override="openrouter/free")
    assert state.failures[0][0] == "openrouter/free"


@pytest.mark.asyncio
async def test_gemini_function_declarations_and_calls_are_normalized(monkeypatch):
    captured = {}

    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, url, *, headers, json):
            captured.update(url=url, headers=headers, payload=json)
            return httpx.Response(
                200,
                request=httpx.Request("POST", url),
                json={
                    "candidates": [
                        {"content": {"parts": [{"functionCall": {"name": "get_cart", "args": {}}}]}}
                    ],
                    "usageMetadata": {"promptTokenCount": 5, "candidatesTokenCount": 2},
                },
            )

    monkeypatch.setattr("src.services.ai_gateway.httpx.AsyncClient", FakeClient)
    provider = GeminiProvider("secret")
    turn = await provider.complete(
        [{"role": "system", "content": "system policy"}, {"role": "user", "content": "cart"}],
        [
            {
                "type": "function",
                "function": {
                    "name": "get_cart",
                    "description": "read",
                    "parameters": {"type": "object"},
                },
            }
        ],
        "gemini-test",
        2,
    )

    assert "key=" not in captured["url"]
    assert captured["headers"]["x-goog-api-key"] == "secret"
    assert captured["payload"]["systemInstruction"]["parts"][0]["text"] == "system policy"
    assert turn.tool_calls[0].name == "get_cart"
    assert (turn.input_tokens, turn.output_tokens) == (5, 2)
