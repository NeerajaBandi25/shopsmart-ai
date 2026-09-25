"""Authenticated persistent cart API."""

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.deps import get_current_user, get_db, require_csrf_token
from src.services.cart_service import CartService

router = APIRouter(prefix="/cart", tags=["Cart"])


class CartItemRequest(BaseModel):
    """Quantity requested for one product."""

    product_id: UUID
    quantity: int = Field(ge=1)


class CartQuantityRequest(BaseModel):
    """Exact quantity for a product identified by the request path."""

    quantity: int = Field(ge=1)


class CartItemResponse(BaseModel):
    """Product details and current cart quantity."""

    product_id: UUID
    name: str
    sku: str
    unit_price: int
    quantity: int
    line_total: int
    stock_quantity: int
    max_purchase_quantity: int


class CartResponse(BaseModel):
    """Current user's cart and server-calculated totals."""

    items: list[CartItemResponse]
    subtotal: int
    currency: str


@router.get("", response_model=CartResponse, summary="Get current user's cart")
async def get_cart(
    current_user_uuid: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CartResponse:
    return CartResponse(**await CartService(db).get_cart(current_user_uuid))


@router.post("/items", response_model=CartResponse, summary="Add items to cart")
async def add_cart_item(
    request: CartItemRequest,
    current_user_uuid: UUID = Depends(get_current_user),
    _csrf_validated: None = Depends(require_csrf_token),
    db: AsyncSession = Depends(get_db),
) -> CartResponse:
    result = await CartService(db).add_item(current_user_uuid, request.product_id, request.quantity)
    return CartResponse(**result)


@router.put("/items/{product_id}", response_model=CartResponse, summary="Set cart item quantity")
async def update_cart_item(
    product_id: UUID,
    request: CartQuantityRequest,
    current_user_uuid: UUID = Depends(get_current_user),
    _csrf_validated: None = Depends(require_csrf_token),
    db: AsyncSession = Depends(get_db),
) -> CartResponse:
    result = await CartService(db).set_item_quantity(
        current_user_uuid, product_id, request.quantity
    )
    return CartResponse(**result)


@router.delete("/items/{product_id}", response_model=CartResponse, summary="Remove cart item")
async def delete_cart_item(
    product_id: UUID,
    current_user_uuid: UUID = Depends(get_current_user),
    _csrf_validated: None = Depends(require_csrf_token),
    db: AsyncSession = Depends(get_db),
) -> CartResponse:
    result = await CartService(db).remove_item(current_user_uuid, product_id)
    return CartResponse(**result)
