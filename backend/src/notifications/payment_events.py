"""Stable payment-domain hook for notification intents."""

from typing import Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.emails.service import EmailOutboxService
from src.emails.templates.order import OrderEmail, OrderLine, TemplateName
from src.emails.model import NotificationOutbox

PaymentEmailEvent = Literal["succeeded", "failed", "cancelled"]


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
    data = OrderEmail(
        order_number=order_number,
        lines=lines,
        subtotal_cents=int(getattr(order, "subtotal_cents")),
        discount_cents=int(getattr(order, "discount_total_cents")),
        total_cents=int(getattr(order, "total_cents")),
        delivery_summary=locality or None,
        recipient_name=str(address.get("recipient_name", "")),
        status_label=event.replace("_", " ").title(),
    )
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
