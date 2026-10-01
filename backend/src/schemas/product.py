"""Public product catalog response schemas."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ProductResponse(BaseModel):
    """Public fields for an active catalog product."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    category: str | None = None
    sku: str
    price: int
    stock_quantity: int
    max_purchase_quantity: int


class ProductPageResponse(BaseModel):
    """A bounded page of catalog products."""

    items: list[ProductResponse]
    skip: int
    limit: int
