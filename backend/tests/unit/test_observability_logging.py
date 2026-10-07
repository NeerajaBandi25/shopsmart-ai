import json
import logging

from src.core.observability import JsonLogFormatter


def test_json_formatter_keeps_ai_acceptance_evidence_but_drops_unapproved_fields():
    record = logging.makeLogRecord(
        {
            "name": "shopsmart.assistant",
            "levelno": logging.INFO,
            "levelname": "INFO",
            "msg": "ASSISTANT_TRACE",
            "routing": {
                "selected_model": "vendor/model:free",
                "scores": {"vendor/model:free": 0.9},
            },
            "eligible_models": ["vendor/model:free"],
            "rejected_models": [{"model": "vendor/other:free", "reason": "no_tools"}],
            "tool_durations_ms": {"search_products": 12.5},
            "source_ids": ["catalog:123"],
            "routing_policy_version": "adaptive-v2",
            "guardrail_result": "passed",
            "raw_prompt": "private user content",
        }
    )

    payload = json.loads(JsonLogFormatter().format(record))
    context = payload["context"]

    assert context["routing"]["selected_model"] == "vendor/model:free"
    assert context["eligible_models"] == ["vendor/model:free"]
    assert context["rejected_models"][0]["reason"] == "no_tools"
    assert context["tool_durations_ms"]["search_products"] == 12.5
    assert context["source_ids"] == ["catalog:123"]
    assert context["routing_policy_version"] == "adaptive-v2"
    assert context["guardrail_result"] == "passed"
    assert "raw_prompt" not in context
