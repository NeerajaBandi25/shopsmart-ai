"""Provider-native tool-call normalization tests use mocked HTTP, never real credentials."""

import json

import httpx
import pytest

from src.services.ai_gateway import (
    GeminiProvider,
    OpenAICompatibleProvider,
    ProviderUnavailable,
)


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


@pytest.mark.asyncio
async def test_provider_rate_limit_is_retryable_before_any_tool_is_executed(monkeypatch):
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
