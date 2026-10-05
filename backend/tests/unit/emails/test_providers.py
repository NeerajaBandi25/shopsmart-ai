"""Provider selection and privacy guarantees."""

import logging

import pytest

from src.emails.providers import CaptureEmailProvider, ConsoleEmailProvider, create_email_provider


def test_capture_is_available_for_tests() -> None:
    assert isinstance(create_email_provider("capture", app_env="test"), CaptureEmailProvider)


def test_console_is_explicitly_restricted_to_nonproduction() -> None:
    assert isinstance(create_email_provider("console", app_env="development"), ConsoleEmailProvider)
    with pytest.raises(RuntimeError, match="restricted"):
        create_email_provider("console", app_env="production")


def test_provider_never_claims_external_delivery_without_implementation() -> None:
    with pytest.raises(RuntimeError, match="adapter is not installed"):
        create_email_provider("resend", app_env="development", resend_api_key="test-placeholder")


@pytest.mark.asyncio
async def test_console_logs_no_recipient_or_body(
    caplog: pytest.LogCaptureFixture, monkeypatch
) -> None:
    provider_logger = logging.getLogger(ConsoleEmailProvider.__module__)
    # Alembic fileConfig disables module loggers during full-suite setup.
    monkeypatch.setattr(provider_logger, "disabled", False)
    monkeypatch.setattr(provider_logger, "propagate", True)
    caplog.set_level(logging.INFO, logger=ConsoleEmailProvider.__module__)
    await ConsoleEmailProvider().send(
        "private.person@example.test", "secret subject", "private body", "<p>private</p>"
    )
    assert any(
        getattr(record, "recipient_domain", None) == "example.test" for record in caplog.records
    )
    assert "private.person" not in caplog.text
    assert "secret subject" not in caplog.text
    assert "private body" not in caplog.text
