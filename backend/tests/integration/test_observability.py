"""Integration tests for request observability and security audit events."""

import json
import logging
import re
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from starlette.requests import Request

from src.core.config import settings
from src.core.email_provider_mock import MockEmailProvider
from src.core.email_provider_prod import ProductionEmailProvider
from src.core.observability import JsonLogFormatter, metrics, security_audit_event
from src.main import general_exception_handler


async def test_request_id_is_generated_logged_and_counted(test_client: AsyncClient, caplog):
    caplog.set_level(logging.INFO)
    before = metrics.snapshot()

    response = await test_client.get("/health")

    request_id = response.headers["x-request-id"]
    assert re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", request_id)
    assert response.json() == {"status": "ok"}

    completion = next(
        record
        for record in caplog.records
        if getattr(record, "event", None) == "request_completed"
        and getattr(record, "request_id", None) == request_id
    )
    structured = json.loads(JsonLogFormatter().format(completion))
    assert structured["request_id"] == request_id
    assert structured["timestamp"]
    assert structured["level"] == "INFO"
    assert structured["message"] == "request_completed"
    assert structured["context"]["method"] == "GET"
    assert structured["context"]["route"] == "/health"
    assert structured["context"]["status_code"] == 200
    assert structured["context"]["duration_ms"] >= 0

    after = metrics.snapshot()
    metric_key = "GET:2xx"
    assert after["requests"][metric_key] == before["requests"].get(metric_key, 0) + 1
    assert after["request_duration_ms"][metric_key]["count"] >= 1


async def test_valid_request_id_is_propagated_and_invalid_id_is_replaced(
    test_client: AsyncClient,
):
    valid_id = "trusted-request_123"
    propagated = await test_client.get("/health", headers={"X-Request-ID": valid_id})
    assert propagated.headers["x-request-id"] == valid_id

    invalid_id = "bad\r\nX-Injected: yes"
    replaced = await test_client.get("/health", headers={"X-Request-ID": invalid_id})
    generated_id = replaced.headers["x-request-id"]
    assert generated_id != invalid_id
    assert re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", generated_id)


async def test_application_error_response_retains_request_id_and_audits_auth_failure(
    test_client: AsyncClient, caplog
):
    caplog.set_level(logging.INFO)
    request_id = "auth-failure-request-1"
    response = await test_client.get("/api/v1/auth/me", headers={"X-Request-ID": request_id})

    assert response.status_code == 401
    assert response.headers["x-request-id"] == request_id
    auth_event = next(
        record
        for record in caplog.records
        if getattr(record, "event", None) == "authentication_failure"
    )
    assert auth_event.request_id == request_id


async def test_auth_audit_events_exclude_credentials_and_tokens(
    test_client: AsyncClient, test_user_data_in_db: dict, caplog
):
    caplog.set_level(logging.INFO)
    password = test_user_data_in_db["password"]
    failed_password = "NeverLogThis-FailedPassword-123!"

    failed = await test_client.post(
        "/api/v1/auth/login",
        json={"email": test_user_data_in_db["email"], "password": failed_password},
    )
    assert failed.status_code == 401

    login = await test_client.post(
        "/api/v1/auth/login",
        json=test_user_data_in_db,
        headers={"X-Request-ID": "login-audit-request"},
    )
    assert login.status_code == 200
    session_id = login.cookies["session_id"]

    denied = await test_client.post(
        "/api/v1/auth/logout",
        cookies={"session_id": session_id},
    )
    assert denied.status_code == 403

    csrf_response = await test_client.get("/api/v1/auth/csrf", cookies={"session_id": session_id})
    assert csrf_response.status_code == 200
    csrf_token = csrf_response.json()["csrf_token"]

    logged_out = await test_client.post(
        "/api/v1/auth/logout",
        cookies={"session_id": session_id},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert logged_out.status_code == 204

    security_records = [
        record
        for record in caplog.records
        if getattr(record, "event", None)
        in {"login_failure", "login_success", "authorization_denied", "logout_success"}
    ]
    event_names = {record.event for record in security_records}
    assert event_names == {
        "login_failure",
        "login_success",
        "authorization_denied",
        "logout_success",
    }
    successful_login = next(
        record for record in security_records if record.event == "login_success"
    )
    successful_login_json = json.loads(JsonLogFormatter().format(successful_login))
    assert successful_login_json["request_id"] == "login-audit-request"
    assert re.fullmatch(r"[a-f0-9]{64}", successful_login.user_ref)
    assert not hasattr(successful_login, "user_id")

    serialized_logs = "\n".join(JsonLogFormatter().format(record) for record in caplog.records)
    assert password not in serialized_logs
    assert failed_password not in serialized_logs
    assert session_id not in serialized_logs
    assert csrf_token not in serialized_logs
    assert test_user_data_in_db["email"] not in serialized_logs
    assert login.json()["user_id"] not in serialized_logs


def test_security_audit_references_correlate_without_raw_identity_or_browser_metadata(
    caplog, monkeypatch
):
    caplog.set_level(logging.INFO)
    monkeypatch.setattr(settings, "secret_key", "audit-key-one")
    identity = "private-user-17"
    ip_address = "203.0.113.42"
    agent = "Custom Browser; email=private-person@example.com; token=private-token"
    for event in ("login_success", "logout_success"):
        security_audit_event(
            event, success=True, user_id=identity, client_ip=ip_address, user_agent=agent
        )
    records = [record for record in caplog.records if record.name == "shopsmart.security"]
    assert len(records) == 2
    assert records[0].user_ref == records[1].user_ref
    assert records[0].client_ref == records[1].client_ref
    for record in records:
        assert re.fullmatch(r"[a-f0-9]{64}", record.user_ref)
        assert re.fullmatch(r"[a-f0-9]{64}", record.client_ref)
        assert not any(hasattr(record, field) for field in ("user_id", "client_ip", "user_agent"))
        serialized = JsonLogFormatter().format(record)
        assert all(raw not in serialized for raw in (identity, ip_address, agent))

    # The same input in a different field must not produce a joinable pseudonym.
    security_audit_event("login_success", success=True, user_id=identity, client_ip=identity)
    assert caplog.records[-1].user_ref != caplog.records[-1].client_ref
    monkeypatch.setattr(settings, "secret_key", "audit-key-two")
    security_audit_event("login_success", success=True, user_id=identity)
    assert caplog.records[-1].user_ref != records[0].user_ref


def test_log_formatter_excludes_raw_identity_fields_even_from_other_callers():
    record = logging.LogRecord("shopsmart.other", logging.INFO, __file__, 0, "event", (), None)
    record.__dict__.update(
        user_id="raw-user", cart_id="raw-cart", client_ip="203.0.113.42", user_agent="raw-agent"
    )
    assert json.loads(JsonLogFormatter().format(record))["context"] == {}


@pytest.mark.parametrize("provider_class", [MockEmailProvider, ProductionEmailProvider])
def test_email_provider_logs_exclude_recipient_subject_and_body(provider_class, caplog, monkeypatch):
    provider_logger = logging.getLogger(provider_class.__module__)
    # Alembic fileConfig disables existing module loggers during full-suite setup.
    # Isolate capture state so privacy is tested whether or not migrations ran first.
    monkeypatch.setattr(provider_logger, "disabled", False)
    monkeypatch.setattr(provider_logger, "propagate", True)
    caplog.set_level(logging.INFO, logger=provider_class.__module__)
    private_values = (
        "private-recipient@example.com",
        "Order confirmation for private-cart-17",
        "Private address and one-time token: never-export-this",
    )
    provider = provider_class()

    assert provider.send_notification(*private_values) is True

    records = [record for record in caplog.records if record.name == provider_class.__module__]
    assert len(records) == 1
    for private_value in private_values:
        assert private_value not in records[0].getMessage()
        assert private_value not in JsonLogFormatter().format(records[0])
    if isinstance(provider, MockEmailProvider):
        # In-memory test inspection remains available without exporting the private payload.
        assert provider.get_sent_emails() == [
            dict(zip(("recipient", "subject", "body"), private_values))
        ]


async def test_registration_and_password_change_audit_events_are_secret_safe(
    test_client: AsyncClient, test_user_data_in_db: dict, caplog
):
    caplog.set_level(logging.INFO)
    registration_email = "audit-registration@example.com"
    registration_password = "AuditRegistration123!"
    weak_email = "audit-weak-password@example.com"

    registered = await test_client.post(
        "/api/v1/auth/register",
        json={"email": registration_email, "password": registration_password},
    )
    rejected = await test_client.post(
        "/api/v1/auth/register",
        json={"email": weak_email, "password": "weak"},
    )
    assert registered.status_code == 201
    assert rejected.status_code == 400

    login = await test_client.post("/api/v1/auth/login", json=test_user_data_in_db)
    session_id = login.cookies["session_id"]
    csrf = await test_client.get("/api/v1/auth/csrf", cookies={"session_id": session_id})
    csrf_token = csrf.json()["csrf_token"]
    new_password = "AuditChangedPassword123!"

    failed_change = await test_client.put(
        "/api/v1/users/password",
        cookies={"session_id": session_id},
        headers={"X-CSRF-Token": csrf_token},
        json={"current_password": "WrongCurrentPassword123!", "new_password": new_password},
    )
    changed = await test_client.put(
        "/api/v1/users/password",
        cookies={"session_id": session_id},
        headers={"X-CSRF-Token": csrf_token},
        json={"current_password": test_user_data_in_db["password"], "new_password": new_password},
    )
    assert failed_change.status_code == 400
    assert changed.status_code == 204

    expected_events = {
        "registration_success",
        "registration_failure",
        "password_change_failure",
        "password_change_success",
    }
    records = [
        record for record in caplog.records if getattr(record, "event", None) in expected_events
    ]
    assert {record.event for record in records} == expected_events

    serialized_logs = "\n".join(JsonLogFormatter().format(record) for record in records)
    for secret in (
        registration_email,
        weak_email,
        registration_password,
        test_user_data_in_db["email"],
        test_user_data_in_db["password"],
        "WrongCurrentPassword123!",
        new_password,
        session_id,
        csrf_token,
    ):
        assert secret not in serialized_logs


def test_security_event_metrics_only_accept_allowlisted_events():
    before = metrics.snapshot()["security_events"].get("login_success", 0)

    security_audit_event("login_success", success=True)
    security_audit_event("unbounded_custom_event", success=True)

    after = metrics.snapshot()["security_events"]
    assert after["login_success"] == before + 1
    assert "unbounded_custom_event" not in after


async def test_unknown_methods_use_bounded_metric_label(test_client: AsyncClient):
    before = metrics.snapshot()

    response = await test_client.request("CUSTOMVERB", "/health")

    assert response.status_code == 405
    after = metrics.snapshot()
    metric_key = "OTHER:4xx"
    assert after["requests"][metric_key] == before["requests"].get(metric_key, 0) + 1
    assert not any("CUSTOMVERB" in key for key in after["requests"])


async def test_metrics_endpoint_is_disabled_without_a_token(test_client: AsyncClient, monkeypatch):
    monkeypatch.setattr(settings, "observability_metrics_token", None)

    response = await test_client.get("/api/v1/observability/metrics")

    assert response.status_code == 404
    assert response.json() == {"detail": "Not found"}


async def test_metrics_endpoint_rejects_missing_and_malformed_authorization(
    test_client: AsyncClient, monkeypatch
):
    monkeypatch.setattr(
        settings,
        "observability_metrics_token",
        "metrics-access-token-0123456789abcdef",
    )

    for headers in ({}, {"Authorization": "Basic credentials"}, {"Authorization": "Bearer"}):
        response = await test_client.get("/api/v1/observability/metrics", headers=headers)
        assert response.status_code == 401
        assert response.json() == {"detail": "Unauthorized"}
        assert response.headers["www-authenticate"] == "Bearer"


async def test_metrics_endpoint_requires_bearer_token_and_returns_bounded_snapshot(
    test_client: AsyncClient, monkeypatch, caplog
):
    caplog.set_level(logging.INFO)
    token = "metrics-access-token-0123456789abcdef"
    monkeypatch.setattr(settings, "observability_metrics_token", token)
    before = metrics.snapshot()

    denied = await test_client.get(
        "/api/v1/observability/metrics", headers={"Authorization": "Bearer wrong-token"}
    )
    assert denied.status_code == 401
    assert denied.headers["www-authenticate"] == "Bearer"

    response = await test_client.get(
        "/api/v1/observability/metrics", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    snapshot = response.json()
    assert snapshot["requests"]["GET:4xx"] == before["requests"].get("GET:4xx", 0) + 1
    assert (
        snapshot["request_duration_ms"]["GET:4xx"]["count"]
        == before["request_duration_ms"].get("GET:4xx", {}).get("count", 0) + 1
    )
    assert snapshot["security_events"] == before["security_events"]
    assert token not in response.text
    assert not any("request_id" in key or "/" in key for key in snapshot["requests"])
    serialized_logs = "\n".join(JsonLogFormatter().format(record) for record in caplog.records)
    assert token not in serialized_logs


async def test_unhandled_exception_log_has_safe_request_context_without_exception_message():
    secret_message = "password=do-not-log-this"
    request = Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "UNTRUSTED-METHOD",
            "scheme": "https",
            "path": "/api/v1/orders/checkout",
            "raw_path": b"/api/v1/orders/checkout",
            "query_string": b"",
            "headers": [],
            "server": ("test", 443),
            "client": ("127.0.0.1", 12345),
            "state": {"request_id": "safe-error-context-1"},
            "route": SimpleNamespace(path="/api/v1/orders/checkout"),
        }
    )

    with patch("src.main.logger.error") as error_log:
        try:
            raise RuntimeError(secret_message)
        except RuntimeError as error:
            response = await general_exception_handler(request, error)

    assert response.status_code == 500
    assert response.body == (
        b'{"detail":"Internal server error","status_code":500,' b'"error_code":"INTERNAL_ERROR"}'
    )
    error_log.assert_called_once()
    assert error_log.call_args.args == ("unhandled_exception",)
    assert error_log.call_args.kwargs["extra"] == {
        "event": "unhandled_exception",
        "exception_type": "RuntimeError",
        "request_id": "safe-error-context-1",
        "method": "OTHER",
        "route": "/api/v1/orders/checkout",
        "status_code": 500,
    }
    record = logging.LogRecord(
        name="src.main",
        level=logging.ERROR,
        pathname=__file__,
        lineno=0,
        msg="unhandled_exception",
        args=(),
        exc_info=error_log.call_args.kwargs["exc_info"],
    )
    record.__dict__.update(error_log.call_args.kwargs["extra"])
    structured = json.loads(JsonLogFormatter().format(record))
    assert structured["request_id"] == "safe-error-context-1"
    assert structured["context"] == {
        "event": "unhandled_exception",
        "exception_type": "RuntimeError",
        "method": "OTHER",
        "route": "/api/v1/orders/checkout",
        "status_code": 500,
    }
    assert "raise RuntimeError" in structured["stack_trace"]
    assert secret_message not in JsonLogFormatter().format(record)
