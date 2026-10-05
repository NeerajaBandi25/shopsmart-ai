"""Provider selection and privacy guarantees."""

import logging

import httpx

import pytest

from src.emails.providers import (
    CaptureEmailProvider,
    ConsoleEmailProvider,
    EmailDeliveryError,
    ResendEmailProvider,
    SMTPEmailProvider,
    create_email_provider,
)
from src.emails.worker import create_worker_provider


def test_capture_is_available_for_tests() -> None:
    assert isinstance(create_email_provider("capture", app_env="test"), CaptureEmailProvider)


def test_console_is_explicitly_restricted_to_nonproduction() -> None:
    assert isinstance(create_email_provider("console", app_env="development"), ConsoleEmailProvider)
    with pytest.raises(RuntimeError, match="restricted"):
        create_email_provider("console", app_env="production")


def test_resend_requires_sender_configuration() -> None:
    with pytest.raises(RuntimeError, match="EMAIL_FROM_ADDRESS"):
        create_email_provider("resend", app_env="development", resend_api_key="test-placeholder")


def test_delivery_worker_refuses_console_sink(monkeypatch) -> None:
    monkeypatch.setenv("EMAIL_PROVIDER", "console")
    monkeypatch.setenv("APP_ENV", "local")
    with pytest.raises(RuntimeError, match="requires Resend or SMTP"):
        create_worker_provider()


@pytest.mark.asyncio
async def test_resend_sends_message_using_configured_sender(monkeypatch) -> None:
    captured = {}

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, *, headers, json):
            captured.update(url=url, headers=headers, json=json)
            return httpx.Response(200, request=httpx.Request("POST", url))

    monkeypatch.setattr("src.emails.providers.httpx.AsyncClient", FakeClient)
    provider = create_email_provider(
        "resend",
        app_env="development",
        resend_api_key="re_test_secret",
        from_address="ShopSmart <orders@example.com>",
    )
    assert isinstance(provider, ResendEmailProvider)
    await provider.send("buyer@example.net", "Order confirmed", "Plain", "<p>HTML</p>")
    assert captured["url"] == "https://api.resend.com/emails"
    assert captured["headers"] == {"Authorization": "Bearer re_test_secret"}
    assert captured["json"] == {
        "from": "ShopSmart <orders@example.com>",
        "to": ["buyer@example.net"],
        "subject": "Order confirmed",
        "text": "Plain",
        "html": "<p>HTML</p>",
    }


@pytest.mark.asyncio
async def test_resend_classifies_throttling_as_retryable(monkeypatch) -> None:
    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, **kwargs):
            return httpx.Response(429, request=httpx.Request("POST", url))

    monkeypatch.setattr("src.emails.providers.httpx.AsyncClient", FakeClient)
    provider = ResendEmailProvider(api_key="re_test_secret", from_address="orders@example.com")
    with pytest.raises(EmailDeliveryError) as error:
        await provider.send("buyer@example.net", "Subject", "Text", "HTML")
    assert error.value.code == "provider_http_429"
    assert error.value.transient is True


@pytest.mark.asyncio
async def test_smtp_uses_tls_and_sends_multipart_order_email(monkeypatch) -> None:
    captured = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            captured.update(host=host, port=port, timeout=timeout)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def ehlo(self):
            captured["ehlo"] = True

        def starttls(self, *, context):
            captured["tls"] = context

        def login(self, username, password):
            captured["auth"] = (username, password)

        def send_message(self, message):
            captured["message"] = message
            return {}

    monkeypatch.setattr("src.emails.providers.smtplib.SMTP", FakeSMTP)
    provider = create_email_provider(
        "smtp",
        app_env="development",
        smtp_host="smtp.gmail.com",
        smtp_port="587",
        smtp_username="sender@gmail.com",
        smtp_password="app-password",
        smtp_use_ssl="false",
        from_address="sender@gmail.com",
    )
    assert isinstance(provider, SMTPEmailProvider)
    await provider.send("buyer@example.net", "Order confirmed", "Plain text", "<p>HTML</p>")
    assert captured["host"] == "smtp.gmail.com"
    assert captured["port"] == 587
    assert captured["auth"] == ("sender@gmail.com", "app-password")
    assert captured["message"]["To"] == "buyer@example.net"
    assert captured["message"].get_body(preferencelist=("plain",)).get_content() == "Plain text\n"
    assert (
        captured["message"].get_body(preferencelist=("html",)).get_content()
        == "<p>HTML</p>\n"
    )


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
