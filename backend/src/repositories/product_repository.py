"""Product repository for data access."""

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.product import PRODUCT_CATEGORIES, Product


class ProductRepository:
    """Repository for Product entity data access."""

    def __init__(self, db: AsyncSession):
        """Initialize repository.

        Args:
            db: Database session
        """
        self.db = db

    async def create_product(
        self,
        name: str,
        description: str | None,
        sku: str,
        price: int,
        stock_quantity: int,
        max_purchase_quantity: int,
        is_active: bool = True,
        category: str | None = None,
    ) -> Product:
        """Create new product.

        Args:
            name: Product name
            description: Product description (optional)
            sku: Stock Keeping Unit (unique identifier)
            price: Price in cents (integer)
            stock_quantity: Available stock quantity
            max_purchase_quantity: Maximum quantity per purchase
            is_active: Whether product is active and available for purchase

        Returns:
            Product: Created product object
        """
        product = Product(
            name=name,
            description=description,
            category=category,
            sku=sku,
            price=price,
            stock_quantity=stock_quantity,
            max_purchase_quantity=max_purchase_quantity,
            is_active=is_active,
        )
        self.db.add(product)
        await self.db.flush()
        return product

    async def get_product_by_id(self, product_id: UUID) -> Product | None:
        """Get product by ID.

        Args:
            product_id: Product ID

        Returns:
            Product | None: Product object or None if not found
        """
        result = await self.db.execute(select(Product).where(Product.id == product_id))
        return result.scalar_one_or_none()

    async def get_product_by_sku(self, sku: str) -> Product | None:
        """Get product by SKU.

        Args:
            sku: Stock Keeping Unit

        Returns:
            Product | None: Product object or None if not found
        """
        result = await self.db.execute(select(Product).where(Product.sku == sku))
        return result.scalar_one_or_none()

    async def get_products(
        self,
        skip: int = 0,
        limit: int = 100,
        active_only: bool = True,
    ) -> list[Product]:
        """Get list of products with pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            active_only: If True, only return active products

        Returns:
            list[Product]: List of product objects
        """
        query = select(Product)
        if active_only:
            query = query.where(Product.is_active.is_(True))
        query = query.order_by(Product.created_at.desc(), Product.id.desc())
        query = query.offset(skip).limit(limit)

        result = await self.db.execute(query)
        return result.scalars().all()

    async def count_active_products(self) -> int:
        result = await self.db.execute(
            select(func.count(Product.id)).where(Product.is_active.is_(True))
        )
        return int(result.scalar_one())

    async def search_active_products(
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
        products, _ = await self.search_active_products_page(
            query_text=query_text,
            category=category,
            brand=brand,
            subcategory=subcategory,
            min_price_cents=min_price_cents,
            max_price_cents=max_price_cents,
            in_stock_only=in_stock_only,
            limit=limit,
        )
        return products

    async def search_active_products_page(
        self,
        query_text: str | None = None,
        category: str | None = None,
        brand: str | None = None,
        subcategory: str | None = None,
        min_price_cents: int | None = None,
        max_price_cents: int | None = None,
        in_stock_only: bool = False,
        skip: int = 0,
        limit: int = 24,
        sort: str = "newest",
    ) -> tuple[list[Product], int]:
        if category is not None and category not in PRODUCT_CATEGORIES:
            return [], 0
        conditions = [Product.is_active.is_(True)]
        if category is not None:
            conditions.append(Product.category == category)
        if brand and brand.strip():
            conditions.append(func.lower(Product.brand) == brand.strip().lower())
        if subcategory and subcategory.strip():
            conditions.append(
                func.lower(Product.specifications["Subcategory"].as_string())
                == subcategory.strip().lower()
            )
        if min_price_cents is not None:
            conditions.append(Product.price >= min_price_cents)
        if max_price_cents is not None:
            conditions.append(Product.price <= max_price_cents)
        if in_stock_only:
            conditions.append(Product.stock_quantity > 0)
        safe_query = query_text.strip()[:160] if query_text and query_text.strip() else None
        if safe_query and safe_query.lower() in {"coding", "programming", "react", "react development"}:
            # A transparent development preset uses published RAM, not an LLM
            # performance claim. Existing category, budget and stock constraints stay intact.
            memory = Product.specifications["RAM"].as_string()
            conditions.append(Product.category == "laptops")
            conditions.append(or_(memory.like("16 GB%"), memory.like("32 GB%")))
            safe_query = None
        if safe_query:
            conditions.append(
                or_(
                    Product.name.ilike(f"%{safe_query}%"),
                    Product.description.ilike(f"%{safe_query}%"),
                    Product.brand.ilike(f"%{safe_query}%"),
                )
            )
        ordering = {
            "newest": (Product.created_at.desc(), Product.id.desc()),
            "price_asc": (Product.price.asc(), Product.id.asc()),
            "price_desc": (Product.price.desc(), Product.id.asc()),
            "name_asc": (func.lower(Product.name).asc(), Product.id.asc()),
        }.get(sort, (Product.created_at.desc(), Product.id.desc()))
        count_result = await self.db.execute(
            select(func.count()).select_from(Product).where(*conditions)
        )
        result = await self.db.execute(
            select(Product)
            .where(*conditions)
            .order_by(*ordering)
            .offset(skip)
            .limit(min(max(limit, 1), 100))
        )
        return list(result.scalars().all()), int(count_result.scalar_one())

    async def update_product(
        self,
        product_id: UUID,
        name: str | None = None,
        description: str | None = None,
        price: int | None = None,
        stock_quantity: int | None = None,
        max_purchase_quantity: int | None = None,
        is_active: bool | None = None,
        category: str | None = None,
    ) -> Product | None:
        """Update product fields.

        Args:
            product_id: Product ID
            name: Product name (optional)
            description: Product description (optional)
            price: Price in cents (optional)
            stock_quantity: Available stock quantity (optional)
            max_purchase_quantity: Maximum quantity per purchase (optional)
            is_active: Whether product is active (optional)

        Returns:
            Product | None: Updated product object or None if not found
        """
        # Get current product
        product = await self.get_product_by_id(product_id)
        if not product:
            return None

        # Update fields if provided
        if name is not None:
            product.name = name
        if description is not None:
            product.description = description
        if price is not None:
            product.price = price
        if stock_quantity is not None:
            product.stock_quantity = stock_quantity
        if max_purchase_quantity is not None:
            product.max_purchase_quantity = max_purchase_quantity
        if is_active is not None:
            product.is_active = is_active
        if category is not None:
            product.category = category

        await self.db.flush()
        return product

    async def delete_product(self, product_id: UUID) -> bool:
        """Delete product (soft delete by setting is_active=False).

        Args:
            product_id: Product ID

        Returns:
            bool: True if product was found and updated, False otherwise
        """
        product = await self.get_product_by_id(product_id)
        if not product:
            return False

        product.is_active = False
        await self.db.flush()
        return True

    async def update_stock(
        self,
        product_id: UUID,
        quantity_change: int,
    ) -> Product | None:
        """Update product stock quantity.

        Args:
            product_id: Product ID
            quantity_change: Change in stock (positive for addition, negative for reduction)

        Returns:
            Product | None: Updated product object or None if not found
        """
        product = await self.get_product_by_id(product_id)
        if not product:
            return None

        new_quantity = product.stock_quantity + quantity_change
        if new_quantity < 0:
            # Not enough stock
            return None

        product.stock_quantity = new_quantity
        await self.db.flush()
        return product
