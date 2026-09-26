"""Authenticated checkout and order history endpoints."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.deps import get_current_user, get_db, require_csrf_token
from src.models.order import Order
from src.services.order_service import OrderService

router = APIRouter(prefix="/orders", tags=["Orders"])


class CheckoutItemRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UUID
    quantity: int = Field(ge=1, le=10000)


class CheckoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[CheckoutItemRequest] = Field(min_length=1, max_length=50)


class OrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: UUID | None
    product_name: str
    product_sku: str
    unit_price_cents: int
    quantity: int
    line_total_cents: int


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    status: str
    total_cents: int
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
    return await OrderService(db).checkout(current_user_id, idempotency_key, items)


@router.get("", response_model=list[OrderResponse], summary="List my orders")
async def list_orders(
    current_user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Order]:
    """Return the authenticated shopper's orders, newest first."""
    return await OrderService(db).get_user_orders(current_user_id)