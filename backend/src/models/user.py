"""User entity model."""

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import BaseModel

if TYPE_CHECKING:
    from src.models.session import Session


class User(BaseModel):
    """User entity representing a registered account."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # Relationships
    sessions: Mapped[list["Session"]] = relationship(
        "Session",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        CheckConstraint(
            "email ~ '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Z|a-z]{2,}$'",
            name="ck_users_email_format",
        ),
        Index("ix_users_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email}>"
