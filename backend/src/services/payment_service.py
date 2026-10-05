"""Idempotent application workflow for sandbox payment sessions and webhooks."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import and_, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.exceptions import AppException, NotFoundError
from src.core.observability import commerce_audit_event
from src.core.payment_limits import (
    FAILED_PAYMENT_RETRY_WINDOW_SECONDS,
    HOSTED_CHECKOUT_SESSION_TTL_SECONDS,
    UNLINKED_PAYMENT_RESERVATION_TTL_SECONDS,
)
from src.models.cart import Cart, CartItem
from src.models.order import Order
from src.models.payment import Payment, PaymentWebhookEvent
from src.models.product import Product
from src.models.user import User
from src.notifications.payment_events import queue_payment_notification
from src.services.product_catalog_cache import invalidate_product_catalog_cache
from src.services.payment_provider import PaymentProvider, VerifiedPaymentEvent

logger = logging.getLogger(__name__)
MAX_PAYMENT_RETRIES = 4


async def reconcile_stale_linked_payment_sessions(
    db: AsyncSession, provider: PaymentProvider, *, limit: int = 25
) -> int:
    """Reconcile old linked sessions against authenticated provider state.

    The local reservation is never timed out while Stripe reports the session open.
    Only a provider-confirmed paid/expired state enters the normal idempotent transition.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(
        seconds=HOSTED_CHECKOUT_SESSION_TTL_SECONDS + 10 * 60
    )
    session_ids = await db.scalars(
        select(Payment.provider_session_id)
        .where(
            Payment.provider == provider.name,
            Payment.provider_session_id.is_not(None),
            Payment.status.in_(["pending", "requires_action"]),
            Payment.updated_at <= cutoff,
        )
        .order_by(Payment.updated_at)
        .limit(limit)
    )
    reconciled = 0
    for session_id in session_ids.all():
        try:
            event = await provider.retrieve_payment_state(session_id)
            if event is not None:
                await PaymentService(db, provider).process_verified_event(event)
                reconciled += 1
            else:
                # The session is still open. Back off instead of polling the oldest
                # batch every five minutes; this timestamp is not used to expire linked holds.
                await db.execute(
                    update(Payment)
                    .where(Payment.provider_session_id == session_id)
                    .values(updated_at=datetime.now(timezone.utc))
                )
                await db.commit()
        except Exception:
            await db.rollback()
            logger.exception(
                "linked_payment_reconciliation_failed",
                extra={
                    "event": "PAYMENT_RECONCILIATION_FAILED",
                    "provider": provider.name,
                },
            )
            try:
                await db.execute(
                    update(Payment)
                    .where(Payment.provider_session_id == session_id)
                    .values(updated_at=datetime.now(timezone.utc))
                )
                await db.commit()
            except Exception:
                await db.rollback()
    return reconciled


async def expire_abandoned_failed_payment_reservations(
    db: AsyncSession, *, limit: int = 100
) -> int:
    """Close orders whose verified failed payment was never retried within 24 hours."""
    cutoff = datetime.now(timezone.utc) - timedelta(
        seconds=FAILED_PAYMENT_RETRY_WINDOW_SECONDS
    )
    candidates = await db.execute(
        select(Payment.id, Payment.order_id)
        .join(Order, Order.id == Payment.order_id)
        .where(
            Payment.status == "failed",
            Payment.updated_at <= cutoff,
            Order.status == "pending_payment",
        )
        .order_by(Payment.updated_at)
        .limit(limit)
    )
    expired = []
    for payment_id, order_id in candidates.all():
        payment = await db.scalar(
            select(Payment)
            .where(Payment.id == payment_id, Payment.status == "failed", Payment.updated_at <= cutoff)
            .with_for_update(skip_locked=True)
        )
        if payment is None:
            continue
        order = await db.scalar(
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.id == order_id, Order.status == "pending_payment")
            .with_for_update(skip_locked=True)
        )
        if order is None:
            continue
        payment.status = "cancelled"
        payment.failure_code = "payment_retry_window_expired"
        payment.failure_message_safe = "The payment retry window expired"
        order.status = "cancelled"
        for item in order.items:
            if item.product_id is not None:
                await db.execute(
                    update(Product)
                    .where(Product.id == item.product_id)
                    .values(stock_quantity=Product.stock_quantity + item.quantity)
                )
        expired.append((order.id, payment.id))

    if not expired:
        await db.rollback()
        return 0
    await db.commit()
    await invalidate_product_catalog_cache()
    for order_id, payment_id in expired:
        commerce_audit_event(
            "PAYMENT_CANCELLED",
            order_id=str(order_id),
            payment_id=str(payment_id),
            provider="stripe",
            status="cancelled",
            error_code="payment_retry_window_expired",
        )
        commerce_audit_event(
            "ORDER_CANCELLED",
            order_id=str(order_id),
            payment_id=str(payment_id),
            provider="stripe",
            status="cancelled",
            error_code="payment_retry_window_expired",
        )
    logger.info(
        "abandoned_failed_payment_reservations_expired",
        extra={"event": "PAYMENT_RETRY_RESERVATIONS_EXPIRED", "count": len(expired)},
    )
    return len(expired)


async def expire_unlinked_payment_reservations(db: AsyncSession, *, limit: int = 100) -> int:
    """Release old stock holds only when no customer-reachable provider session is known.

    Stripe Checkout is configured with a two-hour expiry; this sweep waits three hours
    after the last session-creation attempt to cover a lost/malformed provider response.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(
        seconds=UNLINKED_PAYMENT_RESERVATION_TTL_SECONDS
    )
    candidates = await db.execute(
        select(Order.id, Payment.id)
        .outerjoin(Payment, Payment.order_id == Order.id)
        .where(
            Order.status == "pending_payment",
            or_(
                and_(Payment.id.is_(None), Order.created_at <= cutoff),
                and_(
                    Payment.status == "pending",
                    Payment.provider_session_id.is_(None),
                    Payment.updated_at <= cutoff,
                ),
            ),
        )
        .order_by(Order.created_at)
        .limit(limit)
    )
    expired: list[tuple[UUID, UUID | None]] = []
    for order_id, payment_id in candidates.all():
        payment = None
        if payment_id is not None:
            payment = await db.scalar(
                select(Payment)
                .where(
                    Payment.id == payment_id,
                    Payment.status == "pending",
                    Payment.provider_session_id.is_(None),
                    Payment.updated_at <= cutoff,
                )
                .with_for_update(skip_locked=True)
            )
            if payment is None:
                continue

        order = await db.scalar(
            select(Order)
            .where(Order.id == order_id, Order.status == "pending_payment")
            .with_for_update(skip_locked=True)
        )
        if order is None:
            continue
        if payment is None:
            # A checkout process may have committed the order but not its Payment row.
            # Recheck while holding the order lock; session creation takes this lock too.
            existing_payment = await db.scalar(
                select(Payment.id).where(Payment.order_id == order_id)
            )
            if existing_payment is not None:
                continue
        order.status = "cancelled"
        if payment is not None:
            payment.status = "cancelled"
            payment.failure_code = "unlinked_session_expired"
            payment.failure_message_safe = "Checkout session could not be confirmed in time"
        for item in order.items:
            if item.product_id is not None:
                await db.execute(
                    update(Product)
                    .where(Product.id == item.product_id)
                    .values(stock_quantity=Product.stock_quantity + item.quantity)
                )
        expired.append((order.id, payment.id if payment else None))

    if not expired:
        await db.rollback()
        return 0
    await db.commit()
    await invalidate_product_catalog_cache()
    for order_id, payment_id in expired:
        commerce_audit_event(
            "PAYMENT_CANCELLED",
            order_id=str(order_id),
            payment_id=str(payment_id) if payment_id else None,
            provider="stripe",
            status="cancelled",
            error_code="unlinked_session_expired",
        )
        commerce_audit_event(
            "ORDER_CANCELLED",
            order_id=str(order_id),
            payment_id=str(payment_id) if payment_id else None,
            provider="stripe",
            status="cancelled",
            error_code="unlinked_session_expired",
        )
    logger.info(
        "unlinked_payment_reservations_expired",
        extra={"event": "PAYMENT_RESERVATIONS_EXPIRED", "count": len(expired)},
    )
    return len(expired)


class PaymentService:
    """Coordinate durable payment state with a provider-neutral interface."""

    def __init__(self, db: AsyncSession, provider: PaymentProvider):
        self.db = db
        self.provider = provider

    async def create_or_replay_session(
        self, user_id: UUID, order: Order, request_id: str | None = None
    ) -> tuple[Payment, str]:
        if not self.provider.is_configured():
            raise AppException(
                "Sandbox payments are not configured", 503, "payment_provider_unavailable"
            )
        self.provider.validate_checkout_configuration()
        order_id = order.id
        payment = await self.db.scalar(
            select(Payment).where(Payment.order_id == order_id).with_for_update()
        )
        if payment and payment.user_id != user_id:
            raise NotFoundError("Order not found")
        order = await self.db.scalar(
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.id == order_id, Order.user_id == user_id)
            .with_for_update()
        )
        if order is None:
            raise NotFoundError("Order not found")
        if order.status != "pending_payment":
            if order.status == "paid":
                raise AppException("Order is already paid", 409, "payment_already_complete")
            raise AppException("Order is not awaiting payment", 409, "order_not_payable")
        if payment is None:
            # Serialize the first Payment insert with the expiry worker, which locks
            # the order when it finds an old reservation with no Payment row yet.
            payment = await self.db.scalar(
                select(Payment).where(Payment.order_id == order_id).with_for_update()
            )
        if payment is None:
            payment = Payment(
                order_id=order_id,
                user_id=user_id,
                provider=self.provider.name,
                amount_cents=order.total_cents,
                currency="INR",
                status="pending",
            )
            self.db.add(payment)
            try:
                await self.db.commit()
            except IntegrityError:
                await self.db.rollback()
                payment = await self.db.scalar(select(Payment).where(Payment.order_id == order_id))
                if payment is None:
                    raise
                order = await self.db.scalar(
                    select(Order)
                    .options(selectinload(Order.items))
                    .where(Order.id == order_id, Order.user_id == user_id)
                )
                if order is None:
                    raise NotFoundError("Order not found")

        if payment.status == "succeeded":
            raise AppException("Payment is already complete", 409, "payment_already_complete")
        if payment.status == "refunded":
            raise AppException("Payment was refunded", 409, "payment_refunded")
        if payment.provider_session_url and payment.status in {"pending", "requires_action"}:
            return payment, payment.provider_session_url

        if payment.status == "failed":
            if payment.session_generation >= MAX_PAYMENT_RETRIES:
                raise AppException(
                    "Payment retry limit reached. Contact support for help.",
                    429,
                    "payment_retry_limit",
                )
            payment.session_generation += 1
            payment.status = "pending"
            payment.failure_code = None
            payment.failure_message_safe = None
            payment.provider_session_id = None
            payment.provider_session_url = None
            await self.db.commit()

        # The order is server-priced. The provider receives only the persisted total and INR.
        # Refresh the no-session expiry clock before each outbound attempt. A later sweep
        # must not release stock while this idempotent provider request is in flight.
        payment.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        try:
            session = await self.provider.create_checkout_session(
                order_id=str(order.id),
                amount_cents=payment.amount_cents,
                currency=payment.currency,
                description=f"{len(order.items)} item ShopSmart order",
                idempotency_key=f"shopsmart-order-{order.id}-attempt-{payment.session_generation}",
            )
        except AppException as exc:
            if exc.error_code == "payment_session_rejected":
                await self._close_order_after_provider_rejection(order, payment, request_id)
            raise
        payment.provider_session_id = session.session_id
        payment.provider_session_url = session.checkout_url
        payment.status = "requires_action"
        await self.db.commit()
        logger.info(
            "payment_session_created",
            extra={
                "event": "PAYMENT_SESSION_CREATED",
                "provider": payment.provider,
                "payment_id": str(payment.id),
                "order_id": str(order.id),
                "amount_cents": payment.amount_cents,
                "currency": payment.currency,
                "status": payment.status,
                "request_id": request_id,
            },
        )
        return payment, session.checkout_url

    async def _close_order_after_provider_rejection(
        self, order: Order, payment: Payment, request_id: str | None
    ) -> None:
        """Release inventory only when provider rejection proves no session was created."""
        locked_payment = await self.db.scalar(
            select(Payment).where(Payment.id == payment.id).with_for_update()
        )
        locked_order = await self.db.scalar(
            select(Order).where(Order.id == order.id).with_for_update()
        )
        if (
            locked_payment is None
            or locked_order is None
            or locked_order.status != "pending_payment"
            or locked_payment.provider_session_id is not None
        ):
            return
        locked_payment.status = "failed"
        locked_payment.failure_code = "provider_session_rejected"
        locked_payment.failure_message_safe = "Payment provider rejected checkout"
        locked_order.status = "cancelled"
        await self._release_order_stock(locked_order)
        await self.db.commit()
        await invalidate_product_catalog_cache()
        commerce_audit_event(
            "PAYMENT_FAILED",
            request_id=request_id,
            order_id=str(locked_order.id),
            payment_id=str(locked_payment.id),
            provider=self.provider.name,
            amount_cents=locked_payment.amount_cents,
            currency=locked_payment.currency,
            status=locked_payment.status,
            error_code="provider_session_rejected",
        )
        commerce_audit_event(
            "ORDER_CANCELLED",
            request_id=request_id,
            order_id=str(locked_order.id),
            payment_id=str(locked_payment.id),
            provider=self.provider.name,
            status=locked_order.status,
            error_code="provider_session_rejected",
        )

    async def process_verified_event(
        self, event: VerifiedPaymentEvent, request_id: str | None = None
    ) -> bool:
        """Apply one verified event once; browser redirects never call this method."""
        stock_released = False
        audit_event: str | None = None
        try:
            async with self.db.begin_nested():
                marker = PaymentWebhookEvent(
                    provider=self.provider.name,
                    event_id=event.event_id,
                    event_type=event.event_type,
                )
                self.db.add(marker)
                await self.db.flush()
                payment = await self.db.scalar(
                    select(Payment)
                    .where(Payment.provider_session_id == event.session_id)
                    .with_for_update()
                )
                if payment is None:
                    raise NotFoundError("Payment not found")
                if str(payment.order_id) != event.order_id:
                    raise AppException(
                        "Payment reference mismatch", 400, "payment_reference_mismatch"
                    )
                if payment.amount_cents != event.amount_cents or payment.currency != event.currency:
                    raise AppException("Payment amount mismatch", 400, "payment_amount_mismatch")
                order = await self.db.scalar(
                    select(Order).where(Order.id == payment.order_id).with_for_update()
                )
                if order is None:
                    raise NotFoundError("Order not found")
                if payment.status in {"succeeded", "cancelled"} or order.status == "cancelled":
                    # A terminal payment state cannot be undone by delayed provider events.
                    pass
                else:
                    payment.status = event.status
                    payment.provider_payment_id = event.payment_id or payment.provider_payment_id
                    payment.failure_code = (
                        "provider_payment_failed" if event.status == "failed" else None
                    )
                    payment.failure_message_safe = (
                        "Payment was declined or could not be completed"
                        if event.status == "failed"
                        else None
                    )
                    if event.status == "succeeded":
                        audit_event = "PAYMENT_SUCCEEDED"
                        payment.paid_at = datetime.now(timezone.utc)
                        order.status = "paid"
                        await self._consume_paid_cart_lines(order)
                        await self._publish_notification(
                            "payment_success", order, payment, request_id
                        )
                    elif event.status == "failed":
                        audit_event = "PAYMENT_FAILED"
                        if payment.session_generation >= MAX_PAYMENT_RETRIES:
                            # Once retries are exhausted, close the reservation in the same
                            # transaction as the terminal failure so inventory is available.
                            order.status = "cancelled"
                            await self._release_order_stock(order)
                            stock_released = True
                        await self._publish_notification(
                            "payment_failed", order, payment, request_id
                        )
                    elif event.status == "cancelled":
                        audit_event = "PAYMENT_CANCELLED"
                        order.status = "cancelled"
                        await self._release_order_stock(order)
                        stock_released = True
                        await self._publish_notification(
                            "payment_cancelled", order, payment, request_id
                        )
                marker.processed_at = datetime.now(timezone.utc)
            await self.db.commit()
            if stock_released:
                await invalidate_product_catalog_cache()
            if audit_event:
                commerce_audit_event(
                    audit_event,
                    request_id=request_id,
                    order_id=str(order.id),
                    payment_id=str(payment.id),
                    provider=self.provider.name,
                    amount_cents=payment.amount_cents,
                    currency=payment.currency,
                    status=payment.status,
                )
                if audit_event == "PAYMENT_SUCCEEDED":
                    commerce_audit_event(
                        "PAYMENT_CONFIRMED",
                        request_id=request_id,
                        order_id=str(order.id),
                        payment_id=str(payment.id),
                        provider=self.provider.name,
                        amount_cents=payment.amount_cents,
                        currency=payment.currency,
                        status=payment.status,
                    )
                elif audit_event == "PAYMENT_CANCELLED":
                    commerce_audit_event(
                        "ORDER_CANCELLED",
                        request_id=request_id,
                        order_id=str(order.id),
                        payment_id=str(payment.id),
                        provider=self.provider.name,
                        status=order.status,
                    )
                elif audit_event == "PAYMENT_FAILED" and order.status == "cancelled":
                    commerce_audit_event(
                        "ORDER_CANCELLED",
                        request_id=request_id,
                        order_id=str(order.id),
                        payment_id=str(payment.id),
                        provider=self.provider.name,
                        status=order.status,
                        error_code="payment_retry_limit_reached",
                    )
        except IntegrityError:
            await self.db.rollback()
            duplicate = await self.db.scalar(
                select(PaymentWebhookEvent.id).where(
                    PaymentWebhookEvent.provider == self.provider.name,
                    PaymentWebhookEvent.event_id == event.event_id,
                )
            )
            if duplicate:
                logger.info(
                    "payment_webhook_duplicate",
                    extra={
                        "event": "PAYMENT_WEBHOOK_DUPLICATE",
                        "provider": self.provider.name,
                        "request_id": request_id,
                    },
                )
                return False
            raise
        logger.info(
            "payment_webhook_processed",
            extra={
                "event": "PAYMENT_WEBHOOK_PROCESSED",
                "provider": self.provider.name,
                "event_type": event.event_type,
                "payment_id": str(payment.id),
                "order_id": str(order.id),
                "status": payment.status,
                "request_id": request_id,
            },
        )
        return True

    async def _release_order_stock(self, order: Order) -> None:
        """Return reserved inventory for an order closed before payment succeeds."""
        for item in order.items:
            if item.product_id is None:
                continue
            await self.db.execute(
                update(Product)
                .where(Product.id == item.product_id)
                .values(stock_quantity=Product.stock_quantity + item.quantity)
            )

    async def _consume_paid_cart_lines(self, order: Order) -> None:
        """Subtract purchased quantities on verified success, preserving later additions."""
        cart = await self.db.scalar(
            select(Cart).where(Cart.user_id == order.user_id).with_for_update()
        )
        if cart is None:
            return
        changed = False
        for order_item in order.items:
            if order_item.product_id is None:
                continue
            cart_item = await self.db.scalar(
                select(CartItem)
                .where(
                    CartItem.cart_id == cart.id,
                    CartItem.product_id == order_item.product_id,
                )
                .with_for_update()
            )
            if cart_item is None:
                continue
            remaining = max(0, cart_item.quantity - order_item.quantity)
            if remaining == 0:
                await self.db.delete(cart_item)
            else:
                cart_item.quantity = remaining
            changed = True
        if changed:
            cart.coupon_code = None
            await self.db.flush()

    async def _publish_notification(
        self, event_type: str, order: Order, payment: Payment, request_id: str | None
    ) -> None:
        """Queue notification intent in the verified state transaction.

        Provider delivery occurs later in the email worker and cannot roll back payment.
        An outbox/database failure must abort the webhook transaction so Stripe retries;
        swallowing it here would mark the event processed and lose the notification.
        """
        notification_event = {
            "payment_success": "succeeded",
            "payment_failed": "failed",
            "payment_cancelled": "cancelled",
        }[event_type]
        owner_email = await self.db.scalar(select(User.email).where(User.id == payment.user_id))
        if not owner_email:
            raise ValueError("Payment owner has no notification address")
        await queue_payment_notification(
            self.db,
            notification_event,
            order,
            owner_email,
            request_id,
        )

    async def mark_refunded(self, payment: Payment) -> None:
        """Normalize a provider-confirmed refund after the provider operation succeeds."""
        payment.status = "refunded"
        await self.db.commit()


async def get_payment_for_order(db: AsyncSession, order_id: UUID, user_id: UUID) -> Payment | None:
    result = await db.execute(
        select(Payment).where(Payment.order_id == order_id, Payment.user_id == user_id)
    )
    return result.scalar_one_or_none()
