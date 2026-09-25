"""Public product catalog API."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.deps import get_db
from src.repositories.product_repository import ProductRepository

router = APIRouter(prefix="/products", tags=["Products"])


class ProductResponse(BaseModel):
    """Public fields for an active catalog product."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    sku: str
    price: int
    stock_quantity: int
    max_purchase_quantity: int


class ProductPageResponse(BaseModel):
    """A bounded page of catalog products."""

    items: list[ProductResponse]
    skip: int
    limit: int


@router.get("", response_model=ProductPageResponse, summary="List active products")
async def list_products(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=24, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> ProductPageResponse:
    """Return active products, newest first, without requiring authentication."""
    products = await ProductRepository(db).get_products(skip=skip, limit=limit)
    return ProductPageResponse(items=products, skip=skip, limit=limit)
