"""Authenticated checkout and order history endpoints."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.deps import get_current_user, get_db, require_csrf_token
from src.models.order import Order
from src.services.order_service import OrderService

router = APIRouter(prefix="/orders", tags=["Orders"])


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


@router.post(
    "/checkout",
    response_model=OrderResponse,
    status_code=201,
    summary="Place an order",
)
async def checkout(
    payload: CheckoutRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=1, max_length=255),
    current_user_id: UUID = Depends(get_current_user),
    _: None = Depends(require_csrf_token),
    db: AsyncSession = Depends(get_db),
) -> Order:
    """Place an order using current server-side prices and inventory."""
    items = [(item.product_id, item.quantity) for item in payload.items]
    return await OrderService(db).checkout(
        current_user_id,
        idempotency_key,
        items,
        payload.coupon_code,
        payload.delivery_address.model_dump(),
    )


@router.get("", response_model=list[OrderResponse], summary="List my orders")
async def list_orders(
    current_user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Order]:
    """Return the authenticated shopper's orders, newest first."""
    return await OrderService(db).get_user_orders(current_user_id)
