"""Product entity model."""

from typing import Any

from sqlalchemy import JSON, CheckConstraint, Index, Integer, String
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
        "furniture",
        "sports",
        "toys",
        "books",
        "automotive",
        "pet_supplies",
        "smartphones",
        "headphones",
        "smartwatches",
        "tablets",
        "cameras",
        "televisions",
        "gaming",
        "home_appliances",
        "kitchen_appliances",
        "home_living",
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
    brand: Mapped[str | None] = mapped_column(String(120), nullable=True)
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
    list_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    image_alt: Mapped[str | None] = mapped_column(String(255), nullable=True)
    image_source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    image_creator: Mapped[str | None] = mapped_column(String(255), nullable=True)
    image_license: Mapped[str | None] = mapped_column(String(64), nullable=True)
    image_license_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    image_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    specifications: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
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
        CheckConstraint(
            "list_price IS NULL OR list_price >= price",
            name="ck_products_list_price_not_below_price",
        ),
        CheckConstraint("stock_quantity >= 0", name="ck_products_stock_non_negative"),
        CheckConstraint("max_purchase_quantity >= 1", name="ck_products_max_purchase_positive"),
        Index("ix_products_is_active", "is_active"),
        CheckConstraint(
            "category IS NULL OR category IN ('laptops', 'phones', 'accessories', 'footwear', 'fashion', 'appliances', 'home', 'beauty', 'groceries', 'furniture', 'sports', 'toys', 'books', 'automotive', 'pet_supplies', 'smartphones', 'headphones', 'smartwatches', 'tablets', 'cameras', 'televisions', 'gaming', 'home_appliances', 'kitchen_appliances', 'home_living')",
            name="ck_products_category_canonical",
        ),
        Index("ix_products_category", "category"),
    )

    def __repr__(self) -> str:
        return f"<Product id={self.id} name={self.name} sku={self.sku}>"
