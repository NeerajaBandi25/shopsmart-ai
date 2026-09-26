"""Data access for persistent carts."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.cart import Cart, CartItem
from src.models.product import Product
from src.models.user import User


class CartRepository:
    """Queries and mutations for a user's cart."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_cart(self, user_id: UUID) -> Cart | None:
        result = await self.db.execute(select(Cart).where(Cart.user_id == user_id))
        return result.scalar_one_or_none()

    async def get_or_create_cart(self, user_id: UUID) -> Cart:
        await self.db.execute(select(User.id).where(User.id == user_id).with_for_update())
        cart = await self.get_cart(user_id)
        if cart is None:
            cart = Cart(user_id=user_id)
            self.db.add(cart)
            await self.db.flush()
        return cart

    async def get_product(self, product_id: UUID, *, lock: bool = False) -> Product | None:
        query = select(Product).where(Product.id == product_id)
        if lock:
            query = query.with_for_update()
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_item(self, cart_id: UUID, product_id: UUID) -> CartItem | None:
        result = await self.db.execute(
            select(CartItem)
            .where(CartItem.cart_id == cart_id, CartItem.product_id == product_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def set_item_quantity(self, cart_id: UUID, product_id: UUID, quantity: int) -> None:
        item = await self.get_item(cart_id, product_id)
        if item is None:
            self.db.add(CartItem(cart_id=cart_id, product_id=product_id, quantity=quantity))
        else:
            item.quantity = quantity
        await self.db.flush()

    async def delete_item(self, cart_id: UUID, product_id: UUID) -> None:
        item = await self.get_item(cart_id, product_id)
        if item is not None:
            await self.db.delete(item)
            await self.db.flush()

    async def list_items(self, cart_id: UUID) -> list[tuple[CartItem, Product]]:
        result = await self.db.execute(
            select(CartItem, Product)
            .join(Product, Product.id == CartItem.product_id)
            .where(CartItem.cart_id == cart_id)
            .order_by(CartItem.created_at, CartItem.id)
        )
        return list(result.all())
