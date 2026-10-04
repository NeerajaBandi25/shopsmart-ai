"""Public product catalog API."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.deps import get_db
from src.schemas.product import (
    HeroStoryResponse,
    HomepageResponse,
    ProductPageResponse,
    ProductResponse,
)
from src.services.hero_story_service import HeroStoryService
from src.services.homepage_service import HomepageService
from src.services.product_catalog_service import ProductCatalogService

router = APIRouter(prefix="/products", tags=["Products"])


@router.get("", response_model=ProductPageResponse, summary="List active products")
async def list_products(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=24, ge=1, le=100),
    q: str | None = Query(default=None, max_length=160),
    category: str | None = Query(
        default=None,
        pattern=(
            "^(laptops|smartphones|headphones|smartwatches|tablets|cameras|televisions|"
            "gaming|home_appliances|kitchen_appliances|fashion|footwear|beauty|"
            "accessories|home_living)$"
        ),
    ),
    brand: str | None = Query(default=None, max_length=120),
    subcategory: str | None = Query(default=None, max_length=100),
    min_price_minor: int | None = Query(default=None, ge=0),
    max_price_minor: int | None = Query(default=None, ge=0),
    in_stock_only: bool = Query(default=False),
    sort: Literal["newest", "price_asc", "price_desc", "name_asc"] = Query(
        default="newest"
    ),
    db: AsyncSession = Depends(get_db),
) -> ProductPageResponse:
    """Return active products, newest first, without requiring authentication."""
    if min_price_minor is not None and max_price_minor is not None:
        if min_price_minor > max_price_minor:
            raise HTTPException(status_code=422, detail="Minimum price must not exceed maximum")
    return await ProductCatalogService(db).list_products(
        skip=skip,
        limit=limit,
        query_text=q,
        category=category,
        brand=brand,
        subcategory=subcategory,
        min_price_cents=min_price_minor,
        max_price_cents=max_price_minor,
        in_stock_only=in_stock_only,
        sort=sort,
    )


@router.get("/homepage", response_model=HomepageResponse, summary="Public catalog merchandising")
async def homepage(db: AsyncSession = Depends(get_db)) -> dict:
    return await HomepageService(db).get_homepage()


@router.get(
    "/hero-shortlist",
    response_model=HeroStoryResponse | None,
    summary="Homepage guided shortlist",
)
async def hero_shortlist(db: AsyncSession = Depends(get_db)) -> HeroStoryResponse | None:
    """Build the homepage story from active, in-stock products and published facts."""
    return await HeroStoryService(db).get_story()


@router.get("/{product_id}", response_model=ProductResponse, summary="Get product details")
async def get_product(
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ProductResponse:
    """Return an active product's public details without requiring authentication."""
    product = await ProductCatalogService(db).get_product(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return ProductResponse.model_validate(product)
