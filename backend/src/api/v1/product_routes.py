"""Public product catalog API."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.deps import get_db
from src.schemas.product import ProductPageResponse
from src.services.product_catalog_service import ProductCatalogService

router = APIRouter(prefix="/products", tags=["Products"])


@router.get("", response_model=ProductPageResponse, summary="List active products")
async def list_products(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=24, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> ProductPageResponse:
    """Return active products, newest first, without requiring authentication."""
    return await ProductCatalogService(db).list_products(skip=skip, limit=limit)
