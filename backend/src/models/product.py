"""Product entity model."""

from sqlalchemy import CheckConstraint, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import BaseModel

PRODUCT_CATEGORIES = frozenset(
    {
        "laptops",
        "phones",
        "accessories",
        "footwear",
        "fashion",
        "appliances",
        "home",
        "beauty",
        "groceries",
    }
)


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
    category: Mapped[str | None] = mapped_column(String(32), nullable=True)
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
        CheckConstraint(
            "category IS NULL OR category IN ('laptops', 'phones', 'accessories', 'footwear', 'fashion', 'appliances', 'home', 'beauty', 'groceries')",
            name="ck_products_category_canonical",
        ),
        Index("ix_products_category", "category"),
    )

    def __repr__(self) -> str:
        return f"<Product id={self.id} name={self.name} sku={self.sku}>"
