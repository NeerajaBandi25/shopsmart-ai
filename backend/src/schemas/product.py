"""Public product catalog response schemas."""

from uuid import UUID
from typing import Any
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, computed_field


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

    def _presentation_metadata(self) -> dict[str, Any]:
        value = (self.specifications or {}).get("_presentation")
        return value if isinstance(value, dict) else {}

    @computed_field
    @property
    def delivery(self) -> str | None:
        """Published delivery wording from the authored product record."""
        value = self._presentation_metadata().get("delivery")
        return value if isinstance(value, str) else None

    @computed_field
    @property
    def highlights(self) -> list[str]:
        values = self._presentation_metadata().get("highlights", [])
        if not isinstance(values, list):
            return []
        return [value for value in values if isinstance(value, str)][:8]

    @computed_field
    @property
    def image_gallery(self) -> list[dict[str, str]]:
        """Only artwork references supplied by this product record are public gallery items."""
        values = self._presentation_metadata().get("image_gallery", [])
        if not isinstance(values, list):
            return []
        return [
            {
                "url": value["url"],
                "alt": value.get("alt", self.name),
                **({"role": value["role"]} if isinstance(value.get("role"), str) else {}),
            }
            for value in values
            if isinstance(value, dict)
            and isinstance(value.get("url"), str)
            and isinstance(value.get("alt", self.name), str)
        ][:8]


class ProductPageResponse(BaseModel):
    """A bounded page of catalog products."""

    items: list[ProductResponse]
    skip: int
    limit: int
    total: int


class HeroEvidence(BaseModel):
    label: str
    value: str


class HeroStoryResponse(BaseModel):
    """A compact shortlist and evidence-backed pick from the live catalog."""

    query: str
    budget_minor: int
    candidates: list[ProductResponse]
    recommended_product_id: UUID
    recommendation: str
    evidence: list[HeroEvidence]
    savings_minor: int


class HomepageCategory(BaseModel):
    value: str
    label: str
    count: int


class PublicPromotion(BaseModel):
    """Public merchandising only; codes and private eligibility are deliberately absent."""

    name: str
    description: str | None
    discount_type: Literal["percentage", "fixed"]
    discount_value: int
    ends_at: datetime
    scope_category: str | None


class HomepageResponse(BaseModel):
    categories: list[HomepageCategory]
    featured: list[ProductResponse]
    trending: list[ProductResponse]
    recommendations: list[ProductResponse]
    promotions: list[PublicPromotion]
