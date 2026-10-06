"""Owner-scoped, explicit and removable personalization controls."""

from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.shopper_preference import ShopperPreference

PreferenceLabel = Annotated[str, Field(min_length=1, max_length=80, pattern=r"^[\w .+/-]+$")]


class ExplicitPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preferred_brands: list[PreferenceLabel] = Field(default_factory=list, max_length=10)
    excluded_brands: list[PreferenceLabel] = Field(default_factory=list, max_length=10)
    preferred_budget_cents: int | None = Field(default=None, ge=0, le=1_000_000_000)
    desired_features: list[PreferenceLabel] = Field(default_factory=list, max_length=20)
    use_cases: list[PreferenceLabel] = Field(default_factory=list, max_length=10)
    style_preferences: list[PreferenceLabel] = Field(default_factory=list, max_length=10)


class ShopperPreferenceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, owner_id: UUID) -> dict:
        record = await self.db.scalar(
            select(ShopperPreference).where(ShopperPreference.owner_id == owner_id)
        )
        return {
            "explicit": ExplicitPreferences.model_validate(
                record.explicit if record else {}
            ).model_dump(),
            "inferred": {},
            "behavioral_memory_enabled": False,
        }

    async def replace(self, owner_id: UUID, preferences: ExplicitPreferences) -> dict:
        # Atomic owner-keyed upsert also handles concurrent first-time updates.
        if self.db.bind.dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert
        else:
            from sqlalchemy.dialects.sqlite import insert
        statement = insert(ShopperPreference).values(
            owner_id=owner_id, explicit=preferences.model_dump()
        )
        await self.db.execute(
            statement.on_conflict_do_update(
                index_elements=[ShopperPreference.owner_id],
                set_={"explicit": preferences.model_dump()},
            )
        )
        await self.db.commit()
        return await self.get(owner_id)

    async def clear(self, owner_id: UUID) -> None:
        await self.db.execute(
            delete(ShopperPreference).where(ShopperPreference.owner_id == owner_id)
        )
        await self.db.commit()
