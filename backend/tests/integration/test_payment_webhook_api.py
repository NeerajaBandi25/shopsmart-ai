"""Public webhook API accepts only signed supported events and safely replays."""

import hashlib
import hmac
import json
import time
from uuid import uuid4

import pytest
from httpx import AsyncClient

from src.models.order import Order
from src.models.payment import Payment
from src.models.user import User
from src.services.payment_provider import StripePaymentProvider, get_payment_provider


@pytest.mark.asyncio
async def test_webhook_route_verifies_then_deduplicates_payment_event(
    test_client: AsyncClient, test_db, monkeypatch
):
    from src.services import payment_provider as provider_module

    monkeypatch.setattr(provider_module.settings, "payment_provider", "stripe")
    monkeypatch.setattr(provider_module.settings, "payment_mode", "test")
    user_id = uuid4()
    user = User(id=user_id, email=f"webhook-{uuid4()}@example.com", password_hash="unused")
    order = Order(
        user_id=user_id,
        idempotency_key=f"webhook-{uuid4()}",
        request_hash="b" * 64,
        status="pending_payment",
        subtotal_cents=4321,
        discount_total_cents=0,
        total_cents=4321,
        promotion_snapshot=[],
        delivery_address=None,
    )
    test_db.add_all([user, order])
    await test_db.flush()
    payment = Payment(
        order_id=order.id,
        user_id=user.id,
        provider="stripe",
        provider_session_id="cs_test_api",
        amount_cents=4321,
        currency="INR",
        status="requires_action",
    )
    test_db.add(payment)
    await test_db.commit()

    secret = "whsec_api_test"
    provider = StripePaymentProvider("sk_test_api", secret)
    from src.main import app

    app.dependency_overrides[get_payment_provider] = lambda: provider
    event = {
        "id": "evt_api_once",
        "type": "checkout.session.completed",
        "livemode": False,
        "data": {
            "object": {
                "id": "cs_test_api",
                "client_reference_id": str(order.id),
                "metadata": {"order_id": str(order.id)},
                "payment_status": "paid",
                "amount_total": 4321,
                "currency": "inr",
                "payment_intent": "pi_api_test",
            }
        },
    }
    raw = json.dumps(event, separators=(",", ":")).encode()
    timestamp = str(int(time.time()))
    signature = hmac.new(
        secret.encode(), timestamp.encode() + b"." + raw, hashlib.sha256
    ).hexdigest()
    headers = {"Stripe-Signature": f"t={timestamp},v1={signature}"}
    first = await test_client.post(
        "/api/v1/orders/payments/stripe/webhook", content=raw, headers=headers
    )
    second = await test_client.post(
        "/api/v1/orders/payments/stripe/webhook", content=raw, headers=headers
    )
    assert first.status_code == 200
    assert first.json() == {"received": True, "duplicate": False}
    assert second.status_code == 200
    assert second.json() == {"received": True, "duplicate": True}

    invalid = await test_client.post(
        "/api/v1/orders/payments/stripe/webhook",
        content=raw,
        headers={"Stripe-Signature": f"t={timestamp},v1={'0' * 64}"},
    )
    assert invalid.status_code == 400
    await test_db.refresh(order)
    await test_db.refresh(payment)
    assert order.status == "paid"
    assert payment.status == "succeeded"
