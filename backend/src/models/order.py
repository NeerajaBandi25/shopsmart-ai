"""Order and immutable checkout-line snapshot entities."""

from uuid import UUID

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import BaseModel


class Order(BaseModel):
    """A placed order owned by one shopper."""

    __tablename__ = "orders"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="placed")
    subtotal_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    discount_total_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    promotion_snapshot: Mapped[list[dict[str, object]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    delivery_address: Mapped[dict[str, str] | None] = mapped_column(JSON, nullable=True)
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_orders_user_idempotency_key"),
        CheckConstraint("subtotal_cents >= 0", name="ck_orders_subtotal_non_negative"),
        CheckConstraint(
            "discount_total_cents >= 0 AND discount_total_cents <= subtotal_cents",
            name="ck_orders_discount_within_subtotal",
        ),
        CheckConstraint("total_cents >= 0", name="ck_orders_total_non_negative"),
        CheckConstraint(
            "total_cents = subtotal_cents - discount_total_cents",
            name="ck_orders_pricing_total_consistent",
        ),
        Index("ix_orders_user_created_at", "user_id", "created_at"),
    )


class OrderItem(BaseModel):
    """Product values captured at checkout, independent of later catalog edits."""

    __tablename__ = "order_items"

    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    product_sku: Mapped[str] = mapped_column(String(100), nullable=False)
    product_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    product_image_alt: Mapped[str | None] = mapped_column(String(255), nullable=True)
    unit_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    line_total_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    order: Mapped[Order] = relationship(back_populates="items")

    __table_args__ = (
        CheckConstraint("unit_price_cents >= 0", name="ck_order_items_price_non_negative"),
        CheckConstraint("quantity >= 1", name="ck_order_items_quantity_positive"),
        CheckConstraint("line_total_cents >= 0", name="ck_order_items_total_non_negative"),
    )
