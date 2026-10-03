"""Backend-authoritative promotion definitions."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import BaseModel


class Promotion(BaseModel):
    """A time-bounded, structurally scoped discount offer."""

    __tablename__ = "promotions"

    code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    promotion_type: Mapped[str] = mapped_column(String(16), nullable=False)
    value: Mapped[int] = mapped_column(Integer, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    scope_type: Mapped[str] = mapped_column(String(16), nullable=False)
    scope_category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    scope_product_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=True
    )
    min_cart_total_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_discount_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    eligible_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "promotion_type = 'percentage' AND value BETWEEN 1 AND 100 "
            "OR promotion_type = 'fixed' AND value > 0",
            name="ck_promotions_value_valid",
        ),
        CheckConstraint(
            "scope_type = 'all' AND scope_category IS NULL AND scope_product_id IS NULL "
            "OR scope_type = 'category' AND scope_category IS NOT NULL "
            "AND scope_product_id IS NULL "
            "OR scope_type = 'product' AND scope_category IS NULL "
            "AND scope_product_id IS NOT NULL",
            name="ck_promotions_scope_target_consistent",
        ),
        CheckConstraint(
            "scope_category IS NULL OR scope_category IN "
            "('laptops', 'phones', 'accessories', 'footwear', 'fashion', 'appliances', "
            "'home', 'beauty', 'groceries')",
            name="ck_promotions_scope_category_canonical",
        ),
        CheckConstraint("ends_at > starts_at", name="ck_promotions_window_valid"),
        CheckConstraint(
            "min_cart_total_cents IS NULL OR min_cart_total_cents >= 0",
            name="ck_promotions_minimum_non_negative",
        ),
        CheckConstraint(
            "max_discount_cents IS NULL OR max_discount_cents > 0",
            name="ck_promotions_maximum_positive",
        ),
        UniqueConstraint("code", name="uq_promotions_code"),
        Index("ix_promotions_active_window", "active", "starts_at", "ends_at"),
        Index("ix_promotions_scope_category", "scope_category"),
        Index("ix_promotions_eligible_user", "eligible_user_id"),
    )


Index(
    "uq_promotions_code_lower",
    func.lower(Promotion.code),
    unique=True,
    postgresql_where=text("code IS NOT NULL"),
    sqlite_where=text("code IS NOT NULL"),
)
