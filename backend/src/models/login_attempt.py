"""LoginAttempt entity model for audit and rate limiting."""

from datetime import datetime

from sqlalchemy import (
    INET,
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import BaseModel


class LoginAttempt(BaseModel):
    """LoginAttempt entity for auditing and rate limiting login attempts."""

    __tablename__ = "login_attempts"

    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    ip_address: Mapped[str] = mapped_column(
        INET,
        nullable=False,
    )
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        server_default=func.now(),
    )
    success: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    failure_reason: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "(success = TRUE AND failure_reason IS NULL) OR (success = FALSE AND failure_reason IS NOT NULL)",
            name="ck_login_attempts_reason",
        ),
        Index("ix_login_attempts_ip_attempted_at", "ip_address", "attempted_at"),
        Index("ix_login_attempts_email_attempted_at", "email", "attempted_at"),
    )

    def __repr__(self) -> str:
        return f"<LoginAttempt id={self.id} email={self.email} success={self.success}>"
