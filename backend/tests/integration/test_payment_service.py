"""Database integration tests for idempotent payments and verified transitions."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from src.models.order import Order, OrderItem
from src.models.payment import Payment, PaymentWebhookEvent
from src.models.product import Product
from src.models.cart import Cart, CartItem
from src.models.user import User
from src.core.exceptions import AppException
from src.services.payment_provider import CheckoutSession, VerifiedPaymentEvent
from src.services.payment_service import (
    PaymentService,
    expire_abandoned_failed_payment_reservations,
    expire_unlinked_payment_reservations,
    reconcile_stale_linked_payment_sessions,
)


class FakeProvider:
    name = "fake-test"

    def __init__(self):
        self.sessions = []
        self.reconciled_event = None

    def is_configured(self):
        return True

    def validate_checkout_configuration(self):
        return None

    async def create_checkout_session(self, **kwargs):
        self.sessions.append(kwargs)
        index = len(self.sessions)
        return CheckoutSession(
            f"cs_sandbox_{index}", f"https://checkout.sandbox.test/session-{index}"
        )

    async def retrieve_payment_state(self, session_id):
        return self.reconciled_event

    def verify_webhook(self, raw_body, signature):
        raise NotImplementedError

    async def refund(self, payment_id, amount_cents, idempotency_key):
        raise NotImplementedError


class RejectingProvider(FakeProvider):
    async def create_checkout_session(self, **kwargs):
        raise AppException("Safe normalized rejection", 502, "payment_session_rejected")


@pytest.fixture
async def pending_order(test_db):
    user = User(email=f"pay-{uuid4()}@example.com", password_hash="unused")
    order = Order(
        user_id=user.id,
        idempotency_key=f"pay-{uuid4()}",
        request_hash="a" * 64,
        status="pending_payment",
        subtotal_cents=12500,
        discount_total_cents=500,
        total_cents=12000,
        promotion_snapshot=[],
        delivery_address=None,
        items=[
            OrderItem(
                product_name="Laptop",
                product_sku="PAY-1",
                unit_price_cents=12500,
                quantity=1,
                line_total_cents=12500,
            )
        ],
    )
    user.id = user.id or uuid4()
    order.user_id = user.id
    test_db.add_all([user, order])
    await test_db.commit()
    return user, order


@pytest.mark.asyncio
async def test_checkout_session_is_persisted_and_replayed_once(test_db, pending_order):
    user, order = pending_order
    provider = FakeProvider()
    service = PaymentService(test_db, provider)
    payment, url = await service.create_or_replay_session(user.id, order)
    replay, replay_url = await service.create_or_replay_session(user.id, order)
    assert replay.id == payment.id
    assert replay_url == url
    assert len(provider.sessions) == 1
    assert provider.sessions[0]["amount_cents"] == order.total_cents
    assert provider.sessions[0]["idempotency_key"] == f"shopsmart-order-{order.id}-attempt-0"


@pytest.mark.asyncio
async def test_verified_webhook_marks_order_paid_once(test_db, pending_order):
    user, order = pending_order
    product = Product(
        name="Laptop",
        sku="PAID-CART-1",
        price=12500,
        stock_quantity=2,
        max_purchase_quantity=5,
        is_active=True,
    )
    cart = Cart(user_id=user.id, coupon_code="SAVE20")
    test_db.add_all([product, cart])
    await test_db.flush()
    order.items[0].product_id = product.id
    cart_item = CartItem(cart_id=cart.id, product_id=product.id, quantity=3)
    test_db.add(cart_item)
    await test_db.commit()
    provider = FakeProvider()
    service = PaymentService(test_db, provider)
    payment, _ = await service.create_or_replay_session(user.id, order)
    event = VerifiedPaymentEvent(
        event_id="evt_paid_once",
        event_type="checkout.session.completed",
        session_id="cs_sandbox_1",
        order_id=str(order.id),
        payment_id="pi_sandbox_one",
        amount_cents=order.total_cents,
        currency="INR",
        status="succeeded",
    )
    assert await service.process_verified_event(event) is True
    assert await service.process_verified_event(event) is False
    await test_db.refresh(order)
    await test_db.refresh(payment)
    assert order.status == "paid"
    assert payment.status == "succeeded"
    assert payment.provider_payment_id == "pi_sandbox_one"
    assert await test_db.scalar(select(PaymentWebhookEvent.id)) is not None
    await test_db.refresh(cart_item)
    await test_db.refresh(cart)
    assert cart_item.quantity == 2
    assert cart.coupon_code is None


@pytest.mark.asyncio
async def test_failed_and_cancelled_events_keep_order_pending_for_retry(test_db, pending_order):
    user, order = pending_order
    provider = FakeProvider()
    service = PaymentService(test_db, provider)
    payment, _ = await service.create_or_replay_session(user.id, order)
    failed = VerifiedPaymentEvent(
        event_id="evt_failed",
        event_type="checkout.session.async_payment_failed",
        session_id="cs_sandbox_1",
        order_id=str(order.id),
        payment_id=None,
        amount_cents=order.total_cents,
        currency="INR",
        status="failed",
    )
    assert await service.process_verified_event(failed)
    await test_db.refresh(payment)
    assert payment.status == "failed"
    assert payment.failure_code == "provider_payment_failed"
    assert order.status == "pending_payment"
    retry, _ = await service.create_or_replay_session(user.id, order)
    assert retry.id == payment.id
    assert len(provider.sessions) == 2
    assert provider.sessions[1]["idempotency_key"].endswith("attempt-1")


@pytest.mark.asyncio
async def test_payment_retry_count_is_bounded(test_db, pending_order):
    user, order = pending_order
    provider = FakeProvider()
    payment, _ = await PaymentService(test_db, provider).create_or_replay_session(user.id, order)
    payment.status = "failed"
    payment.session_generation = 4
    await test_db.commit()

    with pytest.raises(AppException, match="Payment retry limit reached") as error:
        await PaymentService(test_db, provider).create_or_replay_session(user.id, order)

    assert error.value.status_code == 429
    assert len(provider.sessions) == 1


@pytest.mark.asyncio
async def test_final_payment_failure_closes_order_and_releases_reserved_stock(
    test_db, pending_order
):
    user, order = pending_order
    provider = FakeProvider()
    service = PaymentService(test_db, provider)
    payment, _ = await service.create_or_replay_session(user.id, order)
    product = Product(
        name="Reserved laptop",
        sku="FAILED-RETRY-RESERVED-1",
        price=12000,
        stock_quantity=7,
        max_purchase_quantity=2,
        is_active=True,
    )
    test_db.add(product)
    await test_db.flush()
    order.items[0].product_id = product.id
    payment.session_generation = 4
    await test_db.commit()

    failed = VerifiedPaymentEvent(
        event_id="evt_final_payment_failure",
        event_type="checkout.session.async_payment_failed",
        session_id="cs_sandbox_1",
        order_id=str(order.id),
        payment_id=None,
        amount_cents=order.total_cents,
        currency="INR",
        status="failed",
    )
    assert await service.process_verified_event(failed)
    await test_db.refresh(order)
    await test_db.refresh(payment)
    await test_db.refresh(product)
    assert payment.status == "failed"
    assert order.status == "cancelled"
    assert product.stock_quantity == 8
    with pytest.raises(AppException, match="Order is not awaiting payment"):
        await service.create_or_replay_session(user.id, order)

    duplicate_failure = VerifiedPaymentEvent(
        event_id="evt_late_failure_after_cancel",
        event_type="checkout.session.async_payment_failed",
        session_id="cs_sandbox_1",
        order_id=str(order.id),
        payment_id=None,
        amount_cents=order.total_cents,
        currency="INR",
        status="failed",
    )
    assert await service.process_verified_event(duplicate_failure)
    await test_db.refresh(product)
    assert product.stock_quantity == 8


@pytest.mark.asyncio
async def test_definitive_provider_rejection_closes_order_and_releases_stock(
    test_db, pending_order
):
    user, order = pending_order
    product = Product(
        name="Rejected checkout laptop",
        sku="PROVIDER-REJECTED-1",
        price=12000,
        stock_quantity=7,
        max_purchase_quantity=2,
        is_active=True,
    )
    test_db.add(product)
    await test_db.flush()
    order.items[0].product_id = product.id
    await test_db.commit()

    with pytest.raises(AppException, match="Safe normalized rejection"):
        await PaymentService(test_db, RejectingProvider()).create_or_replay_session(user.id, order)

    await test_db.refresh(order)
    await test_db.refresh(product)
    payment = await test_db.scalar(select(Payment).where(Payment.order_id == order.id))
    assert order.status == "cancelled"
    assert payment.status == "failed"
    assert payment.failure_code == "provider_session_rejected"
    assert product.stock_quantity == 8


@pytest.mark.asyncio
async def test_stale_unlinked_payment_reservation_expires_and_releases_stock(
    test_db, pending_order
):
    user, order = pending_order
    old = datetime.now(timezone.utc) - timedelta(hours=4)
    product = Product(
        name="Unlinked checkout laptop",
        sku="UNLINKED-SESSION-1",
        price=12000,
        stock_quantity=7,
        max_purchase_quantity=2,
        is_active=True,
    )
    test_db.add(product)
    await test_db.flush()
    order.items[0].product_id = product.id
    order.created_at = old
    payment = Payment(
        order_id=order.id,
        user_id=user.id,
        provider="stripe",
        amount_cents=order.total_cents,
        currency="INR",
        status="pending",
        provider_session_id=None,
        updated_at=old,
    )
    test_db.add(payment)
    await test_db.commit()

    assert await expire_unlinked_payment_reservations(test_db) == 1
    await test_db.refresh(order)
    await test_db.refresh(payment)
    await test_db.refresh(product)
    assert order.status == "cancelled"
    assert payment.status == "cancelled"
    assert payment.failure_code == "unlinked_session_expired"
    assert product.stock_quantity == 8
    assert await expire_unlinked_payment_reservations(test_db) == 0


@pytest.mark.asyncio
async def test_stale_order_without_payment_row_is_safe_to_expire(test_db, pending_order):
    user, order = pending_order
    old = datetime.now(timezone.utc) - timedelta(hours=4)
    product = Product(
        name="Order without payment row",
        sku="MISSING-PAYMENT-ROW-1",
        price=12000,
        stock_quantity=7,
        max_purchase_quantity=2,
        is_active=True,
    )
    test_db.add(product)
    await test_db.flush()
    order.items[0].product_id = product.id
    order.created_at = old
    await test_db.commit()

    assert await expire_unlinked_payment_reservations(test_db) == 1
    await test_db.refresh(order)
    await test_db.refresh(product)
    assert order.status == "cancelled"
    assert product.stock_quantity == 8


@pytest.mark.asyncio
async def test_expired_linked_session_reconciles_and_releases_reserved_stock(
    test_db, pending_order
):
    user, order = pending_order
    product = Product(
        name="Linked stale checkout",
        sku="LINKED-STALE-1",
        price=12000,
        stock_quantity=7,
        max_purchase_quantity=2,
        is_active=True,
    )
    test_db.add(product)
    await test_db.flush()
    order.items[0].product_id = product.id
    payment = Payment(
        order_id=order.id,
        user_id=user.id,
        provider="fake-test",
        amount_cents=order.total_cents,
        currency="INR",
        status="requires_action",
        provider_session_id="cs_sandbox_stale",
        provider_session_url="https://checkout.sandbox.test/session",
        updated_at=datetime.now(timezone.utc) - timedelta(hours=3),
    )
    test_db.add(payment)
    await test_db.commit()
    provider = FakeProvider()
    provider.reconciled_event = VerifiedPaymentEvent(
        event_id="reconcile:cs_sandbox_stale:cancelled",
        event_type="reconciliation.cancelled",
        session_id="cs_sandbox_stale",
        order_id=str(order.id),
        payment_id=None,
        amount_cents=order.total_cents,
        currency="INR",
        status="cancelled",
    )

    assert await reconcile_stale_linked_payment_sessions(test_db, provider) == 1
    await test_db.refresh(order)
    await test_db.refresh(payment)
    await test_db.refresh(product)
    assert order.status == "cancelled"
    assert payment.status == "cancelled"
    assert product.stock_quantity == 8


@pytest.mark.asyncio
async def test_abandoned_verified_failure_expires_after_retry_window(test_db, pending_order):
    user, order = pending_order
    product = Product(
        name="Abandoned failed checkout",
        sku="FAILED-RETRY-WINDOW-1",
        price=12000,
        stock_quantity=7,
        max_purchase_quantity=2,
        is_active=True,
    )
    test_db.add(product)
    await test_db.flush()
    order.items[0].product_id = product.id
    payment = Payment(
        order_id=order.id,
        user_id=user.id,
        provider="fake-test",
        amount_cents=order.total_cents,
        currency="INR",
        status="failed",
        provider_session_id="cs_sandbox_failed",
        updated_at=datetime.now(timezone.utc) - timedelta(hours=25),
    )
    test_db.add(payment)
    await test_db.commit()

    assert await expire_abandoned_failed_payment_reservations(test_db) == 1
    await test_db.refresh(order)
    await test_db.refresh(payment)
    await test_db.refresh(product)
    assert order.status == "cancelled"
    assert payment.status == "cancelled"
    assert payment.failure_code == "payment_retry_window_expired"
    assert product.stock_quantity == 8


@pytest.mark.asyncio
async def test_cancelled_session_releases_stock_once_and_closes_order(test_db, pending_order):
    user, order = pending_order
    provider = FakeProvider()
    service = PaymentService(test_db, provider)
    payment, _ = await service.create_or_replay_session(user.id, order)
    product = Product(
        name="Reserved laptop",
        sku="RESERVED-1",
        price=12000,
        stock_quantity=8,
        max_purchase_quantity=2,
        is_active=True,
    )
    test_db.add(product)
    await test_db.flush()
    order.items[0].product_id = product.id
    await test_db.commit()
    cancelled = VerifiedPaymentEvent(
        event_id="evt_cancelled",
        event_type="checkout.session.expired",
        session_id="cs_sandbox_1",
        order_id=str(order.id),
        payment_id=None,
        amount_cents=order.total_cents,
        currency="INR",
        status="cancelled",
    )
    assert await service.process_verified_event(cancelled)
    await test_db.refresh(payment)
    assert payment.status == "cancelled"
    await test_db.refresh(product)
    assert product.stock_quantity == 9
    cancelled_again = VerifiedPaymentEvent(
        event_id="evt_cancelled_retry",
        event_type="checkout.session.expired",
        session_id="cs_sandbox_1",
        order_id=str(order.id),
        payment_id=None,
        amount_cents=order.total_cents,
        currency="INR",
        status="cancelled",
    )
    assert await service.process_verified_event(cancelled_again)
    await test_db.refresh(product)
    assert product.stock_quantity == 9
    assert order.status == "cancelled"
    with pytest.raises(Exception, match="Order is not awaiting payment"):
        await service.create_or_replay_session(user.id, order)


@pytest.mark.asyncio
async def test_outbox_enqueue_failure_rolls_back_payment_transition_for_webhook_retry(
    test_db, pending_order, monkeypatch
):
    user, order = pending_order
    provider = FakeProvider()
    service = PaymentService(test_db, provider)
    payment, _ = await service.create_or_replay_session(user.id, order)
    event = VerifiedPaymentEvent(
        event_id="evt_outbox_retry",
        event_type="checkout.session.completed",
        session_id="cs_sandbox_1",
        order_id=str(order.id),
        payment_id="pi_outbox_retry",
        amount_cents=order.total_cents,
        currency="INR",
        status="succeeded",
    )

    async def unavailable_outbox(*args, **kwargs):
        raise RuntimeError("temporary database failure")

    monkeypatch.setattr(
        "src.services.payment_service.queue_payment_notification", unavailable_outbox
    )
    with pytest.raises(RuntimeError, match="temporary database failure"):
        await service.process_verified_event(event)

    await test_db.refresh(payment)
    await test_db.refresh(order)
    assert payment.status == "requires_action"
    assert order.status == "pending_payment"
    assert await test_db.scalar(select(PaymentWebhookEvent.id)) is None
