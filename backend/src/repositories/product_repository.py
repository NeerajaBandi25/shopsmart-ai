"""Product repository for data access."""

from uuid import UUID

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.product import Product


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
        result = await self.db.execute(
            select(Product).where(Product.id == product_id)
        )
        return result.scalar_one_or_none()

    async def get_product_by_sku(self, sku: str) -> Product | None:
        """Get product by SKU.

        Args:
            sku: Stock Keeping Unit

        Returns:
            Product | None: Product object or None if not found
        """
        result = await self.db.execute(
            select(Product).where(Product.sku == sku)
        )
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
            query = query.where(Product.is_active == True)
        query = query.offset(skip).limit(limit).order_by(Product.created_at.desc())

        result = await self.db.execute(query)
        return result.scalars().all()

    async def update_product(
        self,
        product_id: UUID,
        name: str | None = None,
        description: str | None = None,
        price: int | None = None,
        stock_quantity: int | None = None,
        max_purchase_quantity: int | None = None,
        is_active: bool | None = None,
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