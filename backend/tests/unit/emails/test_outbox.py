"""Focused outbox reliability and retry checks against an isolated SQLite table."""

from datetime import datetime, timezone
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy import select

from src.emails.model import NotificationOutbox
from src.emails.providers import CaptureEmailProvider, EmailDeliveryError
from src.emails.service import EmailOutboxService
from src.emails.templates.order import OrderEmail, OrderLine
from src.notifications.payment_events import queue_payment_notification


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(NotificationOutbox.__table__.create)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


def sample_email() -> OrderEmail:
    return OrderEmail(
        order_number="SS-20261004-AB12CD34",
        lines=(OrderLine("Phone", 1, 50000),),
        subtotal_cents=50000,
        discount_cents=0,
        total_cents=50000,
    )


@pytest.mark.asyncio
async def test_queue_is_idempotent_and_does_not_commit_callers_transaction(session_factory) -> None:
    async with session_factory() as session:
        service = EmailOutboxService(session)
        first = await service.queue_order_email(
            recipient="shopper@example.test",
            template="order_confirmation",
            data=sample_email(),
            aggregate_id=uuid4(),
            dedupe_key="order:1:confirmation",
        )
        second = await service.queue_order_email(
            recipient="shopper@example.test",
            template="order_confirmation",
            data=sample_email(),
            aggregate_id=first.aggregate_id,
            dedupe_key="order:1:confirmation",
        )
        assert second.id == first.id
        assert session.in_transaction()
        await session.rollback()
    async with session_factory() as session:
        rows = list((await session.scalars(select(NotificationOutbox))).all())
        assert rows == []


@pytest.mark.asyncio
async def test_delivery_records_rendered_message_and_sent_state(session_factory) -> None:
    provider = CaptureEmailProvider()
    async with session_factory() as session:
        await EmailOutboxService(session).queue_order_email(
            recipient="shopper@example.test",
            template="order_confirmation",
            data=sample_email(),
            aggregate_id=uuid4(),
            dedupe_key="order:2:confirmation",
        )
        await session.commit()
        assert await EmailOutboxService(session).deliver_due(provider) == 1
        row = await session.scalar(
            select(NotificationOutbox).where(
                NotificationOutbox.dedupe_key == "order:2:confirmation"
            )
        )
        assert row is not None and row.status == "sent" and row.attempts == 1
        assert row.destination == "[redacted]" and row.payload == {}
        assert "Phone" in provider.messages[0].text_body


class TransientFailureProvider:
    name = "test-failure"

    async def send(self, recipient: str, subject: str, text_body: str, html_body: str) -> None:
        raise EmailDeliveryError("temporarily_unavailable", transient=True)


class PermanentFailureProvider:
    name = "test-permanent"

    async def send(self, recipient: str, subject: str, text_body: str, html_body: str) -> None:
        raise EmailDeliveryError("recipient_rejected", transient=False)


async def enqueue(session, key: str):
    return await EmailOutboxService(session).queue_order_email(
        recipient="shopper@example.test",
        template="payment_success",
        data=sample_email(),
        aggregate_id=uuid4(),
        dedupe_key=key,
    )


@pytest.mark.asyncio
async def test_transient_failure_is_scheduled_bounded_and_safe(session_factory) -> None:
    async with session_factory() as session:
        await enqueue(session, "order:3:payment")
        await session.commit()
        await EmailOutboxService(session).deliver_due(TransientFailureProvider())
        row = await session.scalar(
            select(NotificationOutbox).where(NotificationOutbox.dedupe_key == "order:3:payment")
        )
        assert row is not None
        assert row.status == "pending" and row.attempts == 1
        assert row.last_error_code == "temporarily_unavailable"
        assert row.next_attempt_at is not None


@pytest.mark.asyncio
async def test_permanent_failure_is_terminal(session_factory) -> None:
    async with session_factory() as session:
        await enqueue(session, "order:4:payment")
        await session.commit()
        await EmailOutboxService(session).deliver_due(PermanentFailureProvider())
        row = await session.scalar(
            select(NotificationOutbox).where(NotificationOutbox.dedupe_key == "order:4:payment")
        )
        assert row is not None and row.status == "failed"
        assert row.last_error_code == "recipient_rejected"
        assert row.destination == "[redacted]" and row.payload == {}


@pytest.mark.asyncio
async def test_failed_payment_email_can_be_explicitly_rebuilt_from_order_snapshot(
    session_factory,
) -> None:
    aggregate_id = uuid4()
    async with session_factory() as session:
        row = await EmailOutboxService(session).queue_order_email(
            recipient="shopper@example.test",
            template="payment_success",
            data=sample_email(),
            aggregate_id=aggregate_id,
            dedupe_key=f"order:{aggregate_id}:payment_success",
            request_id="req-email-retry",
        )
        await session.commit()
        await EmailOutboxService(session).deliver_due(PermanentFailureProvider())
        assert row.status == "failed" and row.payload == {}

        restored = await EmailOutboxService(session).requeue_failed_payment_emails(
            request_id="req-email-retry",
            aggregate_id=aggregate_id,
            recipient="shopper@example.test",
            data=sample_email(),
        )
        assert restored == 1
        assert row.status == "pending" and row.destination == "shopper@example.test"
        assert row.attempts == 0 and row.payload["lines"][0]["name"] == "Phone"
        assert await EmailOutboxService(session).deliver_due(CaptureEmailProvider()) == 1


@pytest.mark.asyncio
async def test_invalid_recipient_and_oversized_batch_are_rejected(session_factory) -> None:
    async with session_factory() as session:
        service = EmailOutboxService(session)
        with pytest.raises(ValueError, match="valid email"):
            await service.queue_order_email(
                recipient="attacker@example.test\r\nBcc:x@example.test",
                template="order_confirmation",
                data=sample_email(),
                aggregate_id=uuid4(),
                dedupe_key="bad",
            )
        with pytest.raises(ValueError, match="batch limit"):
            await service.deliver_due(CaptureEmailProvider(), limit=1000)


@pytest.mark.asyncio
async def test_payment_success_queues_confirmation_and_receipt_in_callers_transaction(
    session_factory,
) -> None:
    class Line:
        product_name = "Phone"
        quantity = 1
        line_total_cents = 50000

    class Order:
        id = uuid4()
        created_at = datetime.now(timezone.utc)
        subtotal_cents = 50000
        discount_total_cents = 0
        total_cents = 50000
        delivery_address = {"city": "Hyderabad", "street": "private street"}
        items = [Line()]

    async with session_factory() as session:
        queued = await queue_payment_notification(
            session, "succeeded", Order(), "shopper@example.test", request_id="req-email-1"
        )
        assert {email.template for email in queued} == {"order_confirmation", "payment_success"}
        assert {email.dedupe_key for email in queued} == {
            f"order:{Order.id}:email:order_confirmation",
            f"order:{Order.id}:email:payment_success",
        }
        assert session.in_transaction()
        await session.commit()
    async with session_factory() as session:
        rows = list((await session.scalars(select(NotificationOutbox))).all())
        assert len(rows) == 2
        # Street-level delivery data is not copied into the notification payload.
        assert "street" not in str(rows[0].payload)


@pytest.mark.asyncio
async def test_expired_final_worker_lease_is_terminal(session_factory) -> None:
    async with session_factory() as session:
        row = await enqueue(session, "order:5:payment")
        await session.commit()
        row.status = "sending"
        row.attempts = 8
        row.next_attempt_at = datetime.now(timezone.utc) - timedelta(minutes=3)
        await session.commit()
        assert await EmailOutboxService(session).deliver_due(CaptureEmailProvider()) == 0
        assert row.status == "failed"
        assert row.last_error_code == "delivery_lease_expired"
        assert row.destination == "[redacted]" and row.payload == {}
