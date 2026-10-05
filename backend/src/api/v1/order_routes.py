"""Authenticated checkout and order history endpoints."""

import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.deps import get_current_user, get_db, require_csrf_token
from src.core.exceptions import AppException, NotFoundError
from src.models.order import Order
from src.models.payment import Payment
from src.services.order_service import OrderService
from src.services.payment_provider import PaymentProvider, get_payment_provider
from src.services.payment_service import PaymentService, get_payment_for_order

router = APIRouter(prefix="/orders", tags=["Orders"])
logger = logging.getLogger(__name__)


class CheckoutItemRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UUID
    quantity: int = Field(ge=1, le=10000)


class DeliveryAddressRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipient_name: str = Field(min_length=2, max_length=120)
    phone: str = Field(pattern=r"^\+?[0-9][0-9 ()-]{6,18}$")
    address_line1: str = Field(min_length=4, max_length=200)
    address_line2: str | None = Field(default=None, max_length=200)
    city: str = Field(min_length=2, max_length=100)
    region: str = Field(min_length=2, max_length=100)
    postal_code: str = Field(pattern=r"^[A-Za-z0-9 -]{3,12}$")
    country_code: str = Field(default="IN", pattern="^IN$")

    @field_validator(
        "recipient_name", "phone", "address_line1", "address_line2", "city", "region", "postal_code"
    )
    @classmethod
    def trim_delivery_fields(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class CheckoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[CheckoutItemRequest] = Field(min_length=1, max_length=50)
    coupon_code: str | None = Field(default=None, max_length=64)
    delivery_address: DeliveryAddressRequest

    @field_validator("coupon_code")
    @classmethod
    def normalize_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        from src.services.promotion_service import normalize_coupon_code

        return normalize_coupon_code(value)


class OrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: UUID | None
    product_name: str
    product_sku: str
    product_image_url: str | None
    product_image_alt: str | None
    unit_price_cents: int
    quantity: int
    line_total_cents: int


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    status: str
    subtotal_cents: int
    discount_total_cents: int
    total_cents: int
    delivery_address: dict[str, str | None] | None
    promotion_snapshot: list[dict[str, object]]
    items: list[OrderItemResponse]
    payment_status: str | None = None
    payment_method_label: str | None = None
    checkout_url: str | None = None


class WebhookResponse(BaseModel):
    received: bool
    duplicate: bool = False


@router.post(
    "/checkout",
    response_model=OrderResponse,
    status_code=201,
    summary="Place an order",
)
async def checkout(
    request: Request,
    payload: CheckoutRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=1, max_length=255),
    current_user_id: UUID = Depends(get_current_user),
    _: None = Depends(require_csrf_token),
    db: AsyncSession = Depends(get_db),
    provider: PaymentProvider = Depends(get_payment_provider),
) -> Order:
    """Reserve an authoritative order and return a sandbox-hosted checkout URL."""
    if not provider.is_configured():
        raise AppException(
            "Sandbox payments are not configured", 503, "payment_provider_unavailable"
        )
    provider.validate_checkout_configuration()
    items = [(item.product_id, item.quantity) for item in payload.items]
    order = await OrderService(db).checkout(
        current_user_id,
        idempotency_key,
        items,
        payload.coupon_code,
        payload.delivery_address.model_dump(),
        initial_status="pending_payment",
        request_id=getattr(request.state, "request_id", None),
    )
    service = PaymentService(db, provider)
    payment, checkout_url = await service.create_or_replay_session(
        current_user_id,
        order,
        getattr(request.state, "request_id", None),
    )
    order.payment_status = payment.status
    order.payment_method_label = None
    order.checkout_url = checkout_url
    return order


@router.get("", response_model=list[OrderResponse], summary="List my orders")
async def list_orders(
    current_user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Order]:
    """Return the authenticated shopper's orders, newest first."""
    orders = await OrderService(db).get_user_orders(current_user_id)
    payment_by_order: dict[UUID, Payment] = {}
    if orders:
        payments = await db.scalars(
            select(Payment).where(
                Payment.user_id == current_user_id,
                Payment.order_id.in_([order.id for order in orders]),
            )
        )
        payment_by_order = {payment.order_id: payment for payment in payments}
    for order in orders:
        payment = payment_by_order.get(order.id)
        order.payment_status = payment.status if payment else None
        order.payment_method_label = None
    return orders


@router.get("/{order_id}", response_model=OrderResponse, summary="Get one of my orders")
async def get_order(
    order_id: UUID,
    current_user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Order:
    """Return order and normalized payment state to its owner only."""
    order = await OrderService(db).get_user_order(current_user_id, order_id)
    if order is None:
        raise NotFoundError("Order not found")
    payment = await get_payment_for_order(db, order.id, current_user_id)
    order.payment_status = payment.status if payment else None
    order.payment_method_label = None
    return order


@router.post(
    "/{order_id}/payment/retry",
    response_model=OrderResponse,
    summary="Retry payment for an existing order",
)
async def retry_order_payment(
    order_id: UUID,
    request: Request,
    current_user_id: UUID = Depends(get_current_user),
    _: None = Depends(require_csrf_token),
    db: AsyncSession = Depends(get_db),
    provider: PaymentProvider = Depends(get_payment_provider),
) -> Order:
    """Retry the existing reserved order; never create a second order or stock hold."""
    order = await OrderService(db).get_user_order(current_user_id, order_id)
    if order is None:
        raise NotFoundError("Order not found")
    payment, checkout_url = await PaymentService(db, provider).create_or_replay_session(
        current_user_id,
        order,
        getattr(request.state, "request_id", None),
    )
    order.payment_status = payment.status
    order.payment_method_label = None
    order.checkout_url = checkout_url
    return order


@router.post("/payments/stripe/webhook", response_model=WebhookResponse)
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    provider: PaymentProvider = Depends(get_payment_provider),
) -> WebhookResponse:
    """Consume only signed, bounded Stripe test-mode webhook events."""
    chunks = bytearray()
    async for chunk in request.stream():
        chunks.extend(chunk)
        if len(chunks) > 1_000_000:
            raise AppException("Payment notification is too large", 413, "webhook_too_large")
    raw_body = bytes(chunks)
    event = provider.verify_webhook(raw_body, request.headers.get("Stripe-Signature"))
    request_id = getattr(request.state, "request_id", None)
    if event is None:
        logger.info(
            "payment_webhook_ignored",
            extra={
                "event": "PAYMENT_WEBHOOK_IGNORED",
                "provider": provider.name,
                "request_id": request_id,
            },
        )
        return WebhookResponse(received=True)
    logger.info(
        "payment_webhook_verified",
        extra={
            "event": "PAYMENT_WEBHOOK_VERIFIED",
            "provider": provider.name,
            "event_type": event.event_type,
            "request_id": request_id,
        },
    )
    processed = await PaymentService(db, provider).process_verified_event(event, request_id)
    return WebhookResponse(received=True, duplicate=not processed)
