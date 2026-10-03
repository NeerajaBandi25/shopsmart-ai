"""Public product catalog response schemas."""

from uuid import UUID
from typing import Any

from pydantic import BaseModel, ConfigDict


class ProductResponse(BaseModel):
    """Public fields for an active catalog product."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    category: str | None = None
    brand: str | None
    sku: str
    price: int
    list_price: int | None
    image_url: str | None
    image_alt: str | None
    image_source_url: str | None
    image_creator: str | None
    image_license: str | None
    image_license_url: str | None
    image_sha256: str | None
    specifications: dict[str, Any] | None
    stock_quantity: int
    max_purchase_quantity: int


class ProductPageResponse(BaseModel):
    """A bounded page of catalog products."""

    items: list[ProductResponse]
    skip: int
    limit: int
    total: int
