"""Persistent shopping cart entities."""

from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import BaseModel


class Cart(BaseModel):
    """A user's persistent cart."""

    __tablename__ = "carts"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    items: Mapped[list["CartItem"]] = relationship(
        back_populates="cart",
        cascade="all, delete-orphan",
    )

    __table_args__ = (UniqueConstraint("user_id", name="uq_carts_user_id"),)


class CartItem(BaseModel):
    """A product and quantity in a user's cart."""

    __tablename__ = "cart_items"

    cart_id: Mapped[UUID] = mapped_column(
        ForeignKey("carts.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    cart: Mapped[Cart] = relationship(back_populates="items")

    __table_args__ = (
        UniqueConstraint("cart_id", "product_id", name="uq_cart_items_cart_product"),
        CheckConstraint("quantity >= 1", name="ck_cart_items_quantity_positive"),
    )
