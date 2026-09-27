"""Product catalog use cases and database fallback behavior."""

from sqlalchemy.ext.asyncio import AsyncSession

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
