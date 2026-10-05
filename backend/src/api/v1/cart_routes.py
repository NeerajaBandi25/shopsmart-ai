"""Authenticated persistent cart API."""

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, field_validator
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


class CouponCodeRequest(BaseModel):
    """Bounded coupon request; price and promotion fields are not accepted."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=64)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        from src.services.promotion_service import normalize_coupon_code

        return normalize_coupon_code(value)


class CartItemResponse(BaseModel):
    """Product details and current cart quantity."""

    product_id: UUID
    name: str
    sku: str
    image_url: str | None
    image_alt: str | None
    unit_price: int
    quantity: int
    line_total: int
    stock_quantity: int
    max_purchase_quantity: int


class PromotionResultResponse(BaseModel):
    """Safe eligibility details for a coupon requested by this shopper."""

    promotion_id: UUID | None
    code: str | None
    name: str | None
    eligible: bool
    reason_code: str
    discount_cents: int
    applied_scope: dict[str, str]


class AppliedPromotionResponse(BaseModel):
    """The single selected offer included in the current quote."""

    promotion_id: UUID
    code: str | None
    name: str
    promotion_type: str
    value: int
    discount_cents: int
    applied_scope: dict[str, str]


class CartResponse(BaseModel):
    """Current user's cart and server-calculated totals."""

    items: list[CartItemResponse]
    subtotal: int
    currency: str
    coupon_code: str | None = None
    coupon_evaluation: PromotionResultResponse | None = None
    applied_promotions: list[AppliedPromotionResponse] = Field(default_factory=list)
    discount_total_cents: int = 0
    total_cents: int = 0


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


@router.post("/coupon", response_model=CartResponse, summary="Apply a coupon to the current cart")
async def apply_cart_coupon(
    request: CouponCodeRequest,
    current_user_uuid: UUID = Depends(get_current_user),
    _csrf_validated: None = Depends(require_csrf_token),
    db: AsyncSession = Depends(get_db),
) -> CartResponse:
    result = await CartService(db).apply_coupon(current_user_uuid, request.code)
    return CartResponse(**result)


@router.delete("/coupon", response_model=CartResponse, summary="Remove the current cart coupon")
async def remove_cart_coupon(
    current_user_uuid: UUID = Depends(get_current_user),
    _csrf_validated: None = Depends(require_csrf_token),
    db: AsyncSession = Depends(get_db),
) -> CartResponse:
    result = await CartService(db).remove_coupon(current_user_uuid)
    return CartResponse(**result)
