"""Product entity model."""

from sqlalchemy import String, Integer, Numeric, CheckConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import BaseModel


class Product(BaseModel):
    """Product entity representing an item for sale."""

    __tablename__ = "products"

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )
    sku: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
    )
    price: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    stock_quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    max_purchase_quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=5,
    )
    is_active: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
    )

    # Relationships
    # order_items: Mapped[list["OrderItem"]] = relationship(
    #     "OrderItem",
    #     back_populates="product",
    #     cascade="all, delete-orphan",
    # )

    __table_args__ = (
        CheckConstraint("price >= 0", name="ck_products_price_non_negative"),
        CheckConstraint("stock_quantity >= 0", name="ck_products_stock_non_negative"),
        CheckConstraint("max_purchase_quantity >= 1", name="ck_products_max_purchase_positive"),
        Index("ix_products_is_active", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<Product id={self.id} name={self.name} sku={self.sku}>"
