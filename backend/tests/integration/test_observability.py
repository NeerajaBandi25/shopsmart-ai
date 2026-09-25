"""Integration tests for request observability and security audit events."""

import json
import logging
import re

from httpx import AsyncClient

from src.core.observability import JsonLogFormatter, metrics, security_audit_event


async def test_request_id_is_generated_logged_and_counted(
    test_client: AsyncClient, caplog
):
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
    response = await test_client.get(
        "/api/v1/auth/me", headers={"X-Request-ID": request_id}
    )

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

    csrf_response = await test_client.get(
        "/api/v1/auth/csrf", cookies={"session_id": session_id}
    )
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
    assert successful_login.user_id

    serialized_logs = "\n".join(JsonLogFormatter().format(record) for record in caplog.records)
    assert password not in serialized_logs
    assert failed_password not in serialized_logs
    assert session_id not in serialized_logs
    assert csrf_token not in serialized_logs
    assert test_user_data_in_db["email"] not in serialized_logs


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

    login = await test_client.post(
        "/api/v1/auth/login", json=test_user_data_in_db
    )
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
        record
        for record in caplog.records
        if getattr(record, "event", None) in expected_events
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
