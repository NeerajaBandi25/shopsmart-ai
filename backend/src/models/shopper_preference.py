"""Only shopper-authored preferences are persisted; behavior is never promoted implicitly."""

from uuid import UUID

from sqlalchemy import JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import BaseModel


class ShopperPreference(BaseModel):
    __tablename__ = "shopper_preferences"

    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    explicit: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
