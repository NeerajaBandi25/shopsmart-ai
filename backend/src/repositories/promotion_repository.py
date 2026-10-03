"""Persistence queries for backend-owned promotion records."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.promotion import Promotion


class PromotionRepository:
    """Read current promotion candidates without exposing write operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_code(self, code: str) -> Promotion | None:
        result = await self.db.execute(select(Promotion).where(func.upper(Promotion.code) == code))
        return result.scalar_one_or_none()

    async def list_automatic(self, user_id: UUID, now: datetime) -> list[Promotion]:
        result = await self.db.execute(
            select(Promotion)
            .where(
                Promotion.active.is_(True),
                Promotion.starts_at <= now,
                Promotion.ends_at > now,
                Promotion.code.is_(None),
                or_(Promotion.eligible_user_id.is_(None), Promotion.eligible_user_id == user_id),
            )
            .order_by(Promotion.id)
        )
        return list(result.scalars().all())

    async def list_active(self, user_id: UUID, now: datetime) -> list[Promotion]:
        result = await self.db.execute(
            select(Promotion)
            .where(
                Promotion.active.is_(True),
                Promotion.starts_at <= now,
                Promotion.ends_at > now,
                or_(Promotion.eligible_user_id.is_(None), Promotion.eligible_user_id == user_id),
            )
            .order_by(Promotion.id)
        )
        return list(result.scalars().all())
