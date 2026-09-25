"""Order persistence operations used by checkout and order history."""

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.order import Order
from src.models.product import Product


class OrderRepository:
    """Database operations for transactional order workflows."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_idempotency_key(self, user_id: UUID, key: str) -> Order | None:
        result = await self.db.execute(
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.user_id == user_id, Order.idempotency_key == key)
        )
        return result.scalar_one_or_none()

    async def lock_products(self, product_ids: list[UUID]) -> dict[UUID, Product]:
        result = await self.db.execute(
            select(Product)
            .where(Product.id.in_(product_ids))
            .order_by(Product.id)
            .with_for_update()
        )
        return {product.id: product for product in result.scalars().all()}

    async def decrement_stock(self, product_id: UUID, quantity: int) -> bool:
        result = await self.db.execute(
            update(Product)
            .where(
                Product.id == product_id,
                Product.is_active.is_(True),
                Product.stock_quantity >= quantity,
            )
            .values(stock_quantity=Product.stock_quantity - quantity)
            .execution_options(synchronize_session="fetch")
        )
        return result.rowcount == 1

    async def add_order(self, order: Order) -> None:
        self.db.add(order)
        await self.db.flush()

    async def get_user_orders(self, user_id: UUID) -> list[Order]:
        result = await self.db.execute(
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.user_id == user_id)
            .order_by(Order.created_at.desc(), Order.id.desc())
        )
        return list(result.scalars().all())