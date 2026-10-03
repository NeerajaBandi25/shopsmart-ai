"""Product catalog use cases and database fallback behavior."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.product import Product
from src.repositories.product_repository import ProductRepository
from src.schemas.product import ProductPageResponse
from src.services.product_catalog_cache import ProductCatalogCache


class ProductCatalogService:
    """Serve public catalog pages from Redis when available, otherwise PostgreSQL."""

    def __init__(self, db: AsyncSession, cache: ProductCatalogCache | None = None):
        self.repository = ProductRepository(db)
        self.cache = cache or ProductCatalogCache()

    async def list_products(self, skip: int, limit: int) -> ProductPageResponse:
        lookup = await self.cache.get_page(skip, limit)
        if lookup.page is not None:
            return lookup.page

        products = await self.repository.get_products(skip=skip, limit=limit)
        page = ProductPageResponse(items=products, skip=skip, limit=limit)
        await self.cache.set_page(skip, limit, lookup.generation, page)
        return page

    async def search_products(
        self,
        query_text: str | None = None,
        category: str | None = None,
        min_price_cents: int | None = None,
        max_price_cents: int | None = None,
        in_stock_only: bool = False,
        limit: int = 20,
    ) -> list[Product]:
        """Run a filtered catalog query without reusing an unfiltered page cache entry."""
        return await self.repository.search_active_products(
            query_text=query_text,
            category=category,
            min_price_cents=min_price_cents,
            max_price_cents=max_price_cents,
            in_stock_only=in_stock_only,
            limit=limit,
        )

    async def get_product(self, product_id: UUID) -> Product | None:
        return await self.repository.get_product_by_id(product_id)
