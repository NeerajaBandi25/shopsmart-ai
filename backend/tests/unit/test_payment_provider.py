"""Sandbox provider guardrails and normalized event mapping tests."""

import hashlib
import hmac
import json
import time

import pytest

from src.core.exceptions import AppException
from src.core.payment_limits import HOSTED_CHECKOUT_SESSION_TTL_SECONDS
from src.services.payment_provider import StripePaymentProvider, normalize_stripe_status


def test_normalizes_only_supported_stripe_checkout_states():
    assert normalize_stripe_status("checkout.session.completed", "paid") == "succeeded"
    assert normalize_stripe_status("checkout.session.async_payment_failed", None) == "failed"
    assert normalize_stripe_status("checkout.session.expired", None) == "cancelled"
    assert normalize_stripe_status("checkout.session.completed", "unpaid") is None
    assert normalize_stripe_status("payment_intent.succeeded", "paid") is None


def test_live_keys_cannot_enable_sandbox_provider():
    provider = StripePaymentProvider("sk_live_do_not_use", "whsec_test")
    assert provider.is_configured() is False


def test_provider_requires_explicit_stripe_test_mode(monkeypatch):
    from src.services import payment_provider as module

    monkeypatch.setattr(module.settings, "payment_provider", "stripe")
    monkeypatch.setattr(module.settings, "payment_mode", "live")
    provider = StripePaymentProvider("sk_test_local", "whsec_test")
    assert provider.is_configured() is False
    monkeypatch.setattr(module.settings, "payment_provider", "disabled")
    monkeypatch.setattr(module.settings, "payment_mode", "test")
    assert provider.is_configured() is False


def test_http_local_return_urls_are_development_only(monkeypatch):
    from src.services import payment_provider as module

    monkeypatch.setattr(module.settings, "app_env", "production")
    with pytest.raises(AppException, match="HTTPS"):
        module._return_url("http://localhost:3000/checkout", "order-1", success=False)
    monkeypatch.setattr(module.settings, "app_env", "development")
    assert module._return_url("http://localhost:3000/checkout", "order-1", success=False)


def test_checkout_configuration_preflight_rejects_invalid_return_url(monkeypatch):
    from src.services import payment_provider as module

    monkeypatch.setattr(module.settings, "payment_provider", "stripe")
    monkeypatch.setattr(module.settings, "payment_mode", "test")
    monkeypatch.setattr(module.settings, "app_env", "production")
    monkeypatch.setattr(module.settings, "payment_success_url", "http://localhost:3000/complete")
    monkeypatch.setattr(module.settings, "payment_cancel_url", "https://shop.example/checkout")
    monkeypatch.setattr(module.settings, "cors_origins", ["https://shop.example"])

    provider = StripePaymentProvider("sk_test_local", "whsec_test")
    with pytest.raises(AppException) as error:
        provider.validate_checkout_configuration()
    assert error.value.error_code == "payment_config_invalid"


def test_webhook_signature_and_replay_window_are_verified():
    secret = "whsec_sandbox"
    provider = StripePaymentProvider("sk_test_local", secret)
    timestamp = str(int(time.time()))
    payload = {
        "id": "evt_123",
        "type": "checkout.session.completed",
        "livemode": False,
        "data": {
            "object": {
                "id": "cs_test_123",
                "client_reference_id": "order-1",
                "metadata": {"order_id": "order-1"},
                "payment_status": "paid",
                "amount_total": 4321,
                "currency": "inr",
                "payment_intent": "pi_test_123",
            }
        },
    }
    raw = json.dumps(payload, separators=(",", ":")).encode()
    digest = hmac.new(secret.encode(), timestamp.encode() + b"." + raw, hashlib.sha256).hexdigest()
    verified = provider.verify_webhook(raw, f"t={timestamp},v1={digest}")
    assert verified is not None
    assert verified.status == "succeeded"
    assert verified.amount_cents == 4321
    assert verified.currency == "INR"
    with pytest.raises(AppException, match="Invalid payment notification"):
        provider.verify_webhook(raw, f"t={timestamp},v1={'0' * 64}")
    stale = str(int(time.time()) - 600)
    stale_digest = hmac.new(
        secret.encode(), stale.encode() + b"." + raw, hashlib.sha256
    ).hexdigest()
    with pytest.raises(AppException, match="Expired payment notification"):
        provider.verify_webhook(raw, f"t={stale},v1={stale_digest}")


def test_unknown_signed_event_is_acknowledged_without_domain_transition():
    secret = "whsec_sandbox"
    provider = StripePaymentProvider("sk_test_local", secret)
    timestamp = str(int(time.time()))
    raw = json.dumps({"id": "evt_unknown", "type": "customer.updated", "livemode": False}).encode()
    digest = hmac.new(secret.encode(), timestamp.encode() + b"." + raw, hashlib.sha256).hexdigest()
    assert provider.verify_webhook(raw, f"t={timestamp},v1={digest}") is None


@pytest.mark.parametrize("livemode", [True, None])
def test_live_or_unmarked_webhook_events_are_rejected(livemode):
    secret = "whsec_sandbox"
    provider = StripePaymentProvider("sk_test_local", secret)
    timestamp = str(int(time.time()))
    payload = {"id": "evt_mode", "type": "customer.updated"}
    if livemode is not None:
        payload["livemode"] = livemode
    raw = json.dumps(payload).encode()
    digest = hmac.new(secret.encode(), timestamp.encode() + b"." + raw, hashlib.sha256).hexdigest()
    with pytest.raises(AppException, match="Live payment notifications are not accepted"):
        provider.verify_webhook(raw, f"t={timestamp},v1={digest}")


def test_provider_does_not_accept_unconfigured_or_invalid_amounts():
    provider = StripePaymentProvider("sk_test_local", "whsec_local")
    assert provider.is_configured()
    invalid = StripePaymentProvider("sk_live_local", "whsec_local")
    assert invalid.is_configured() is False


@pytest.mark.asyncio
async def test_invalid_amount_is_rejected_before_provider_network_call():
    provider = StripePaymentProvider("sk_test_local", "whsec_local")
    for amount_cents in (0, 49, 100_000_000):
        with pytest.raises(AppException, match="Order amount is not supported"):
            await provider.create_checkout_session(
                order_id="order",
                amount_cents=amount_cents,
                currency="INR",
                description="test",
                idempotency_key="order-key",
            )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "payment_status", "expected"),
    [("complete", "paid", "succeeded"), ("expired", "unpaid", "cancelled")],
)
async def test_retrieved_provider_state_is_bound_to_authoritative_session(
    monkeypatch, status, payment_status, expected
):
    from src.services import payment_provider as module

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "id": "cs_test_reconcile",
                "status": status,
                "payment_status": payment_status,
                "client_reference_id": "order-1",
                "metadata": {"order_id": "order-1"},
                "amount_total": 54321,
                "currency": "inr",
                "payment_intent": "pi_test_1",
            }

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, **kwargs):
            return Response()

    monkeypatch.setattr(module.httpx, "AsyncClient", Client)
    event = await StripePaymentProvider("sk_test_local", "whsec_local").retrieve_payment_state(
        "cs_test_reconcile"
    )
    assert event.status == expected
    assert event.order_id == "order-1"
    assert event.amount_cents == 54321
    assert event.currency == "INR"


@pytest.mark.asyncio
async def test_retrieved_open_unpaid_session_is_not_reconciled(monkeypatch):
    from src.services import payment_provider as module

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "id": "cs_test_open",
                "status": "open",
                "payment_status": "unpaid",
                "client_reference_id": "order-1",
                "metadata": {},
                "amount_total": 54321,
                "currency": "inr",
            }

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, **kwargs):
            return Response()

    monkeypatch.setattr(module.httpx, "AsyncClient", Client)
    event = await StripePaymentProvider("sk_test_local", "whsec_local").retrieve_payment_state(
        "cs_test_open"
    )
    assert event is None


@pytest.mark.asyncio
async def test_concurrent_idempotency_conflict_is_retryable_not_definitive(monkeypatch):
    from src.services import payment_provider as module

    class ConflictResponse:
        def raise_for_status(self):
            request = module.httpx.Request("POST", "https://api.stripe.com/v1/checkout/sessions")
            response = module.httpx.Response(409, request=request)
            raise module.httpx.HTTPStatusError("conflict", request=request, response=response)

    class ConflictClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, **kwargs):
            return ConflictResponse()

    monkeypatch.setattr(module.httpx, "AsyncClient", ConflictClient)
    provider = StripePaymentProvider("sk_test_local", "whsec_test")
    with pytest.raises(AppException) as error:
        await provider.create_checkout_session(
            order_id="order-123",
            amount_cents=54321,
            currency="INR",
            description="test",
            idempotency_key="shopsmart-order-order-123-attempt-0",
        )
    assert error.value.error_code == "payment_session_failed"


@pytest.mark.asyncio
async def test_test_checkout_uses_server_amount_idempotency_and_order_bound_return_urls(
    monkeypatch,
):
    from src.services import payment_provider as module

    calls = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"id": "cs_test_abc", "url": "https://checkout.stripe.com/test"}

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, **kwargs):
            calls.update(url=url, **kwargs)
            return FakeResponse()

    monkeypatch.setattr(module.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(
        module.settings, "payment_success_url", "https://shop.test/checkout/complete"
    )
    monkeypatch.setattr(
        module.settings,
        "payment_cancel_url",
        "https://shop.test/checkout/complete?payment=cancelled",
    )
    monkeypatch.setattr(module.settings, "cors_origins", ["https://shop.test"])
    provider = StripePaymentProvider("sk_test_local", "whsec_local")
    session = await provider.create_checkout_session(
        order_id="order-123",
        amount_cents=54321,
        currency="INR",
        description="2 item order",
        idempotency_key="shopsmart-order-order-123-attempt-0",
    )
    assert session.session_id == "cs_test_abc"
    assert calls["headers"]["Idempotency-Key"] == "shopsmart-order-order-123-attempt-0"
    form = calls["data"]
    assert form["line_items[0][price_data][unit_amount]"] == "54321"
    assert int(form["expires_at"]) >= int(time.time()) + HOSTED_CHECKOUT_SESSION_TTL_SECONDS - 2
    assert form["payment_method_types[0]"] == "card"
    assert form["success_url"] == (
        "https://shop.test/checkout/complete?order_id=order-123&session_id={CHECKOUT_SESSION_ID}"
    )
    assert form["cancel_url"] == (
        "https://shop.test/checkout/complete?payment=cancelled&order_id=order-123"
    )
