"""Transactional outbox enqueueing and bounded at-least-once delivery."""

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.emails.model import NotificationOutbox
from src.emails.providers import EmailDeliveryError, EmailProvider
from src.emails.templates.order import OrderEmail, OrderLine, TemplateName, render_order_email

logger = logging.getLogger(__name__)
MAX_ATTEMPTS = 8
MAX_PAYLOAD_BYTES = 48_000
LEASE_SECONDS = 120
_EMAIL_RE = re.compile(r"^[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+$")
_ALLOWED_TEMPLATES = {
    "order_confirmation",
    "payment_success",
    "payment_failed",
    "order_cancelled",
    "order_status",
}


def _safe_domain(address: str) -> str:
    return address.rpartition("@")[2].lower() if "@" in address else "invalid"


def _payload_from_order(data: OrderEmail) -> dict[str, Any]:
    return {
        "order_number": data.order_number,
        "recipient_name": data.recipient_name,
        "lines": [
            {
                "name": line.name,
                "quantity": line.quantity,
                "line_total_cents": line.line_total_cents,
            }
            for line in data.lines
        ],
        "subtotal_cents": data.subtotal_cents,
        "discount_cents": data.discount_cents,
        "total_cents": data.total_cents,
        "delivery_summary": data.delivery_summary,
        "order_url": data.order_url,
        "status_label": data.status_label,
    }


def _data_from_payload(payload: dict[str, Any]) -> OrderEmail:
    return OrderEmail(
        order_number=str(payload["order_number"]),
        recipient_name=str(payload.get("recipient_name", "")),
        lines=tuple(OrderLine(**line) for line in payload.get("lines", [])),
        subtotal_cents=int(payload["subtotal_cents"]),
        discount_cents=int(payload["discount_cents"]),
        total_cents=int(payload["total_cents"]),
        delivery_summary=payload.get("delivery_summary"),
        order_url=str(payload.get("order_url", "/orders")),
        status_label=payload.get("status_label"),
    )


class EmailOutboxService:
    """Queue within caller's transaction; deliver separately after commit."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def queue_order_email(
        self,
        *,
        recipient: str,
        template: TemplateName,
        data: OrderEmail,
        aggregate_id: UUID,
        dedupe_key: str,
        request_id: str | None = None,
    ) -> NotificationOutbox:
        """Flush a semantic email intent without committing the caller's transaction."""
        if not _EMAIL_RE.fullmatch(recipient) or len(recipient) > 320:
            raise ValueError("A valid email destination is required")
        if template not in _ALLOWED_TEMPLATES:
            raise ValueError("Unsupported transactional email template")
        if not dedupe_key or len(dedupe_key) > 200:
            raise ValueError("A bounded idempotency key is required")
        safe_data = _payload_from_order(data)
        if len(json.dumps(safe_data, ensure_ascii=False).encode("utf-8")) > MAX_PAYLOAD_BYTES:
            raise ValueError("Email payload exceeds the outbox size limit")
        existing = await self.db.scalar(
            select(NotificationOutbox).where(NotificationOutbox.dedupe_key == dedupe_key)
        )
        if existing:
            return existing

        now = datetime.now(timezone.utc)
        row = NotificationOutbox(
            id=uuid4(),
            created_at=now,
            updated_at=now,
            event_type=template,
            aggregate_id=aggregate_id,
            destination=recipient,
            template=template,
            payload=safe_data,
            dedupe_key=dedupe_key,
            request_id=request_id[:128] if request_id else None,
            status="pending",
            attempts=0,
            next_attempt_at=datetime.now(timezone.utc),
        )
        dialect = self.db.get_bind().dialect.name
        insert = (
            pg_insert if dialect == "postgresql" else sqlite_insert if dialect == "sqlite" else None
        )
        if insert is None:
            raise RuntimeError("Email outbox supports PostgreSQL and SQLite transaction stores")
        statement = (
            insert(NotificationOutbox)
            .values(
                id=row.id,
                created_at=now,
                updated_at=now,
                event_type=row.event_type,
                aggregate_id=row.aggregate_id,
                destination=row.destination,
                template=row.template,
                payload=row.payload,
                dedupe_key=row.dedupe_key,
                request_id=row.request_id,
                status=row.status,
                attempts=row.attempts,
                next_attempt_at=row.next_attempt_at,
            )
            .on_conflict_do_nothing(index_elements=[NotificationOutbox.dedupe_key])
            .returning(NotificationOutbox.id)
        )
        inserted_id = (await self.db.execute(statement)).scalar_one_or_none()
        if inserted_id is None:
            existing = await self.db.scalar(
                select(NotificationOutbox).where(NotificationOutbox.dedupe_key == dedupe_key)
            )
            if existing is None:
                raise RuntimeError("Outbox dedupe conflict could not be resolved")
            return existing
        row = await self.db.get(NotificationOutbox, inserted_id)
        assert row is not None
        logger.info(
            "EMAIL_QUEUED",
            extra={
                "request_id": request_id,
                "template": template,
                "provider": "outbox",
                "recipient_domain": _safe_domain(recipient),
                "attempt": 0,
            },
        )
        return row

    async def deliver_due(self, provider: EmailProvider, *, limit: int = 20) -> int:
        """Claim and attempt a bounded batch; each email has a finite retry budget."""
        if not 1 <= limit <= 100:
            raise ValueError("Delivery batch limit must be between 1 and 100")
        delivered = 0
        for _ in range(limit):
            row = await self._claim_one()
            if row is None:
                break
            started = datetime.now(timezone.utc)
            recipient_domain = _safe_domain(row.destination)
            try:
                template = row.template
                if template not in _ALLOWED_TEMPLATES:
                    raise EmailDeliveryError("unsupported_template", transient=False)
                subject, plain, html = render_order_email(template, _data_from_payload(row.payload))
                logger.info(
                    "EMAIL_SEND_STARTED",
                    extra={
                        "request_id": row.request_id,
                        "template": template,
                        "provider": provider.name,
                        "recipient_domain": _safe_domain(row.destination),
                        "attempt": row.attempts,
                    },
                )
                await provider.send(row.destination, subject, plain, html)
            except EmailDeliveryError as exc:
                await self._finish_failure(row, provider.name, exc.code, exc.transient)
            except ValueError:
                await self._finish_failure(
                    row, provider.name, "invalid_template_payload", transient=False
                )
            except (
                Exception
            ) as exc:  # noqa: BLE001 - provider exceptions are normalized at this boundary.
                # Do not log exception text: SDK errors can embed addresses, message fragments or credentials.
                logger.error(
                    "EMAIL_PROVIDER_UNEXPECTED_FAILURE",
                    extra={
                        "request_id": row.request_id,
                        "template": row.template,
                        "provider": provider.name,
                        "error_type": type(exc).__name__,
                        "attempt": row.attempts,
                    },
                )
                await self._finish_failure(
                    row, provider.name, f"provider_unexpected_{type(exc).__name__}", transient=True
                )
            else:
                row.status = "sent"
                row.sent_at = datetime.now(timezone.utc)
                row.last_error_code = None
                # Keep the dedupe/audit stub, but discard message content and address after delivery.
                row.destination = "[redacted]"
                row.payload = {}
                await self.db.commit()
                delivered += 1
                logger.info(
                    "EMAIL_SENT",
                    extra={
                        "request_id": row.request_id,
                        "template": row.template,
                        "provider": provider.name,
                        "recipient_domain": recipient_domain,
                        "attempt": row.attempts,
                        "duration_ms": int(
                            (datetime.now(timezone.utc) - started).total_seconds() * 1000
                        ),
                    },
                )
        return delivered

    async def _claim_one(self) -> NotificationOutbox | None:
        now = datetime.now(timezone.utc)
        async with self.db.begin():
            row = await self.db.scalar(
                select(NotificationOutbox)
                .where(
                    or_(
                        (
                            (NotificationOutbox.status == "pending")
                            & (NotificationOutbox.attempts < MAX_ATTEMPTS)
                            & (NotificationOutbox.next_attempt_at <= now)
                        ),
                        (
                            (NotificationOutbox.status == "sending")
                            & (NotificationOutbox.next_attempt_at <= now)
                        ),
                    ),
                )
                .order_by(NotificationOutbox.next_attempt_at, NotificationOutbox.created_at)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if row is None:
                return None
            if row.attempts >= MAX_ATTEMPTS:
                # A worker may have crashed on the final leased attempt; finalize it on lease expiry.
                recipient_domain = _safe_domain(row.destination)
                row.status = "failed"
                row.last_error_code = "delivery_lease_expired"
                row.destination = "[redacted]"
                row.payload = {}
                await self.db.flush()
                logger.error(
                    "EMAIL_FAILED",
                    extra={
                        "request_id": row.request_id,
                        "template": row.template,
                        "provider": "unknown_after_worker_crash",
                        "recipient_domain": recipient_domain,
                        "attempt": row.attempts,
                        "error_code": row.last_error_code,
                    },
                )
                return None
            row.status = "sending"
            row.attempts += 1
            row.next_attempt_at = now + timedelta(seconds=LEASE_SECONDS)
            await self.db.flush()
        # Materialize before session starts next transaction (and caller can safely reuse it).
        await self.db.refresh(row)
        return row

    async def _finish_failure(
        self, row: NotificationOutbox, provider: str, code: str, transient: bool
    ) -> None:
        row.last_error_code = code[:64]
        if not transient or row.attempts >= MAX_ATTEMPTS:
            row.status = "failed"
            recipient_domain = _safe_domain(row.destination)
            row.destination = "[redacted]"
            row.payload = {}
            logger.error(
                "EMAIL_FAILED",
                extra={
                    "request_id": row.request_id,
                    "template": row.template,
                    "provider": provider,
                    "recipient_domain": recipient_domain,
                    "attempt": row.attempts,
                    "error_code": code,
                },
            )
        else:
            # Bounded exponential retry (1m, 2m, 4m ... capped at 6h) with a finite attempt count.
            delay = min(60 * (2 ** (row.attempts - 1)), 6 * 60 * 60)
            row.status = "pending"
            row.next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
            logger.warning(
                "EMAIL_RETRY_SCHEDULED",
                extra={
                    "request_id": row.request_id,
                    "template": row.template,
                    "provider": provider,
                    "recipient_domain": _safe_domain(row.destination),
                    "attempt": row.attempts,
                    "error_code": code,
                },
            )
        await self.db.commit()
