"""Provider-neutral payment and webhook idempotency records.

Import this module from the model registry before generating/applying its migration.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import BaseModel


class Payment(BaseModel):
    """A normalized payment attempt associated with exactly one order."""

    __tablename__ = "payments"

    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_payment_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_session_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    session_generation: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    failure_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    failure_message_safe: Mapped[str | None] = mapped_column(String(255), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("order_id", name="uq_payments_order_id"),
        UniqueConstraint("provider_payment_id", name="uq_payments_provider_payment_id"),
        UniqueConstraint("provider_session_id", name="uq_payments_provider_session_id"),
        Index("ix_payments_user_created_at", "user_id", "created_at"),
        CheckConstraint("amount_cents > 0", name="ck_payments_amount_positive"),
        CheckConstraint("currency = 'INR'", name="ck_payments_currency_inr"),
        CheckConstraint(
            "status IN ('pending', 'requires_action', 'succeeded', 'failed', 'cancelled', "
            "'refunded')",
            name="ck_payments_status_normalized",
        ),
        CheckConstraint("session_generation >= 0", name="ck_payments_generation_non_negative"),
    )


class PaymentWebhookEvent(BaseModel):
    """Unique verified-provider event IDs prevent retrying a state transition."""

    __tablename__ = "payment_webhook_events"

    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("provider", "event_id", name="uq_payment_webhook_provider_event"),
    )
