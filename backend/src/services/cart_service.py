"""Business rules for the authenticated persistent cart."""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import ValidationError
from src.repositories.cart_repository import CartRepository


class CartService:
    """Validate cart mutations and calculate totals from current product data."""

    def __init__(self, db: AsyncSession):
        self.repository = CartRepository(db)
        self.db = db

    async def get_cart(self, user_id: UUID) -> dict:
        cart = await self.repository.get_cart(user_id)
        if cart is None:
            return {"items": [], "subtotal": 0, "currency": "USD"}
        return await self._cart_response(cart.id)

    async def add_item(self, user_id: UUID, product_id: UUID, quantity: int) -> dict:
        cart = await self.repository.get_or_create_cart(user_id)
        product = await self._get_available_product(product_id)
        existing = await self.repository.get_item(cart.id, product_id)
        requested_quantity = quantity + (existing.quantity if existing else 0)
        self._validate_quantity(
            requested_quantity, product.stock_quantity, product.max_purchase_quantity
        )
        await self.repository.set_item_quantity(cart.id, product_id, requested_quantity)
        await self.db.commit()
        return await self._cart_response(cart.id)

    async def set_item_quantity(self, user_id: UUID, product_id: UUID, quantity: int) -> dict:
        cart = await self.repository.get_or_create_cart(user_id)
        product = await self._get_available_product(product_id)
        self._validate_quantity(quantity, product.stock_quantity, product.max_purchase_quantity)
        await self.repository.set_item_quantity(cart.id, product_id, quantity)
        await self.db.commit()
        return await self._cart_response(cart.id)

    async def remove_item(self, user_id: UUID, product_id: UUID) -> dict:
        cart = await self.repository.get_cart(user_id)
        if cart is None:
            return {"items": [], "subtotal": 0, "currency": "USD"}
        await self.repository.delete_item(cart.id, product_id)
        await self.db.commit()
        return await self._cart_response(cart.id)

    async def _get_available_product(self, product_id: UUID):
        product = await self.repository.get_product(product_id, lock=True)
        if product is None or not product.is_active:
            raise HTTPException(status_code=404, detail="Product not found")
        return product

    @staticmethod
    def _validate_quantity(quantity: int, stock_quantity: int, max_purchase_quantity: int) -> None:
        if quantity < 1:
            raise ValidationError("Quantity must be at least 1", "invalid_quantity")
        if quantity > stock_quantity:
            raise ValidationError(
                "Requested quantity exceeds available stock", "insufficient_stock"
            )
        if quantity > max_purchase_quantity:
            raise ValidationError("Requested quantity exceeds the purchase limit", "quantity_limit")

    async def _cart_response(self, cart_id: UUID) -> dict:
        items = []
        subtotal = 0
        for cart_item, product in await self.repository.list_items(cart_id):
            line_total = product.price * cart_item.quantity
            subtotal += line_total
            items.append(
                {
                    "product_id": product.id,
                    "name": product.name,
                    "sku": product.sku,
                    "unit_price": product.price,
                    "quantity": cart_item.quantity,
                    "line_total": line_total,
                    "stock_quantity": product.stock_quantity,
                    "max_purchase_quantity": product.max_purchase_quantity,
                }
            )
        return {"items": items, "subtotal": subtotal, "currency": "USD"}
