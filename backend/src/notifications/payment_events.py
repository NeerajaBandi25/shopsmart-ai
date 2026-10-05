"""Stable payment-domain hook for notification intents."""

import logging
from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.emails.model import NotificationOutbox
from src.emails.service import EmailOutboxService
from src.emails.templates.order import OrderEmail, OrderLine, TemplateName
from src.models.order import Order
from src.models.payment import Payment
from src.models.user import User

logger = logging.getLogger(__name__)

PaymentEmailEvent = Literal["succeeded", "failed", "cancelled"]


def _order_email_data(order: object, event: PaymentEmailEvent) -> OrderEmail:
    order_id = getattr(order, "id", None)
    if not isinstance(order_id, UUID):
        raise ValueError("Payment notification requires a persisted order")
    created = getattr(order, "created_at", None)
    order_number = (
        "SS-"
        + (created.strftime("%Y%m%d") if created else "ORDER")
        + "-"
        + str(order_id).replace("-", "")[:8].upper()
    )
    address = getattr(order, "delivery_address", None) or {}
    locality = ", ".join(str(address[key]) for key in ("city", "region") if address.get(key))
    lines = tuple(
        OrderLine(
            name=str(item.product_name),
            quantity=int(item.quantity),
            line_total_cents=int(item.line_total_cents),
        )
        for item in (getattr(order, "items", None) or [])
    )
    return OrderEmail(
        order_number=order_number,
        lines=lines,
        subtotal_cents=int(getattr(order, "subtotal_cents")),
        discount_cents=int(getattr(order, "discount_total_cents")),
        total_cents=int(getattr(order, "total_cents")),
        delivery_summary=locality or None,
        recipient_name=str(address.get("recipient_name", "")),
        status_label=event.replace("_", " ").title(),
    )


async def queue_payment_notification(
    db: AsyncSession,
    event: PaymentEmailEvent,
    order: object,
    owner_email: str,
    request_id: str | None = None,
) -> tuple[NotificationOutbox, ...]:
    """Queue event-specific message(s) in verified transaction; never commits it."""
    templates: dict[str, tuple[TemplateName, ...]] = {
        "succeeded": ("order_confirmation", "payment_success"),
        "failed": ("payment_failed",),
        "cancelled": ("order_cancelled",),
    }
    if event not in templates:
        raise ValueError("Unsupported payment notification event")
    order_id = getattr(order, "id", None)
    if not isinstance(order_id, UUID):
        raise ValueError("Payment notification requires a persisted order")
    data = _order_email_data(order, event)
    outbox = EmailOutboxService(db)
    queued = []
    for template in templates[event]:
        queued.append(
            await outbox.queue_order_email(
                recipient=owner_email,
                template=template,
                data=data,
                aggregate_id=order_id,
                dedupe_key=f"order:{order_id}:email:{template}",
                request_id=request_id,
            )
        )
    return tuple(queued)


async def requeue_failed_payment_emails(
    db: AsyncSession, request_id: str
) -> int:
    """Rebuild failed payment-success emails after an explicit local operator retry."""
    if not request_id or len(request_id) > 128:
        raise ValueError("A valid request ID is required")
    rows = list(
        (
            await db.scalars(
                select(NotificationOutbox).where(
                    NotificationOutbox.request_id == request_id,
                    NotificationOutbox.template.in_(("order_confirmation", "payment_success")),
                    NotificationOutbox.status == "failed",
                )
            )
        ).all()
    )
    aggregate_ids = {row.aggregate_id for row in rows}
    if not rows or len(aggregate_ids) != 1:
        return 0
    order_id = next(iter(aggregate_ids))
    order = await db.scalar(
        select(Order).options(selectinload(Order.items)).where(Order.id == order_id)
    )
    if order is None:
        return 0
    payment = await db.scalar(
        select(Payment).where(Payment.order_id == order_id, Payment.status == "succeeded")
    )
    if payment is None:
        return 0
    owner = await db.get(User, order.user_id)
    if owner is None:
        return 0
    restored = await EmailOutboxService(db).requeue_failed_payment_emails(
        request_id=request_id,
        aggregate_id=order_id,
        recipient=owner.email,
        data=_order_email_data(order, "succeeded"),
    )
    logger.info(
        "EMAIL_FAILED_PAYMENT_REQUEUED",
        extra={"request_id": request_id, "template_count": restored},
    )
    return restored
