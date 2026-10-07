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

    async def list_products(
        self,
        skip: int,
        limit: int,
        query_text: str | None = None,
        category: str | None = None,
        brand: str | None = None,
        subcategory: str | None = None,
        min_price_cents: int | None = None,
        max_price_cents: int | None = None,
        in_stock_only: bool = False,
        sort: str = "newest",
    ) -> ProductPageResponse:
        is_default_query = (
            not any(
                (
                    query_text,
                    category,
                    brand,
                    subcategory,
                    min_price_cents,
                    max_price_cents,
                    in_stock_only,
                )
            )
            and sort == "newest"
        )
        lookup = await self.cache.get_page(skip, limit) if is_default_query else None
        if lookup and lookup.page is not None:
            ids = [UUID(value) for value in lookup.page.product_ids]
            current = await self.repository.get_active_products_by_ids(ids) if ids else []
            products_by_id = {
                (product["id"] if isinstance(product, dict) else product.id): product
                for product in current
            }
            ordered = [
                products_by_id[product_id] for product_id in ids if product_id in products_by_id
            ]
            total = await self.repository.count_active_products()
            return ProductPageResponse(items=ordered, skip=skip, limit=limit, total=total)

        if is_default_query:
            products = await self.repository.get_products(skip=skip, limit=limit)
            total = await self.repository.count_active_products()
        else:
            products, total = await self.repository.search_active_products_page(
                query_text=query_text,
                category=category,
                brand=brand,
                subcategory=subcategory,
                min_price_cents=min_price_cents,
                max_price_cents=max_price_cents,
                in_stock_only=in_stock_only,
                skip=skip,
                limit=limit,
                sort=sort,
            )
        page = ProductPageResponse(items=products, skip=skip, limit=limit, total=total)
        if is_default_query and lookup:
            await self.cache.set_page(
                skip,
                limit,
                lookup.generation,
                [
                    str(product["id"] if isinstance(product, dict) else product.id)
                    for product in products
                ],
                total,
            )
        return page

    async def search_products(
        self,
        query_text: str | None = None,
        category: str | None = None,
        brand: str | None = None,
        subcategory: str | None = None,
        min_price_cents: int | None = None,
        max_price_cents: int | None = None,
        in_stock_only: bool = False,
        limit: int = 20,
    ) -> list[Product]:
        """Run a filtered catalog query without reusing an unfiltered page cache entry."""
        return await self.repository.search_active_products(
            query_text=query_text,
            category=category,
            brand=brand,
            subcategory=subcategory,
            min_price_cents=min_price_cents,
            max_price_cents=max_price_cents,
            in_stock_only=in_stock_only,
            limit=limit,
        )

    async def get_product(self, product_id: UUID) -> Product | None:
        product = await self.repository.get_product_by_id(product_id)
        return product if product and product.is_active else None
