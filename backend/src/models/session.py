"""Session entity model."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import BaseModel


class Session(BaseModel):
    """Session entity representing an authenticated browser session."""

    __tablename__ = "sessions"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    last_activity: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        server_default=func.now(),
    )
    ip_address: Mapped[str] = mapped_column(
        INET().with_variant(String(45), "sqlite"),
        nullable=False,
    )
    user_agent: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="sessions",
    )

    __table_args__ = (
        Index("ix_sessions_user_id_is_active", "user_id", "is_active"),
        Index("ix_sessions_last_activity", "last_activity"),
    )

    def __repr__(self) -> str:
        return f"<Session id={self.id} user_id={self.user_id} is_active={self.is_active}>"
