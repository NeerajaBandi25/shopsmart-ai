"""Opt-in live provider tool-call smoke test; never runs with ordinary CI credentials."""

import os

import pytest

from src.core.config import settings
from src.services.ai_gateway import ProviderGateway
from src.services.ai_governance import DataClassification

_LIVE_TEST_ENABLED = (
    os.getenv("RUN_LIVE_AI_TESTS", "").lower() == "true"
    and os.getenv("AI_TEST_CREDENTIALS_NONPRODUCTION", "").lower() == "true"
)


@pytest.mark.asyncio
@pytest.mark.skipif(
    not _LIVE_TEST_ENABLED,
    reason="requires explicit opt-in and confirmation that provider credentials are non-production",
)
async def test_live_provider_executes_a_function_call():
    """Make a minimal PUBLIC request and require a real provider-native function call."""
    assert settings.ai_provider in {"openai_compatible", "openrouter", "groq", "gemini"}
    tools = [
        {
            "type": "function",
            "function": {
                "name": "ping_shopsmart",
                "description": "Return a basic availability signal.",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            },
        }
    ]
    turn, provider, model = await ProviderGateway().tool_turn(
        [
            {
                "role": "system",
                "content": "Call ping_shopsmart exactly once. Do not answer in prose.",
            },
            {"role": "user", "content": "Check the assistant tool connection."},
        ],
        tools,
        DataClassification.PUBLIC,
    )

    assert provider == settings.ai_provider
    assert model
    assert any(call.name == "ping_shopsmart" for call in turn.tool_calls)
