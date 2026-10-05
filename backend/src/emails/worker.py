"""Standalone transactional email outbox worker (`python -m src.emails.worker`)."""

import asyncio
import logging
import os

from src.database import AsyncSessionLocal
from src.emails.providers import EmailProvider, create_email_provider
from src.emails.service import EmailOutboxService
from src.notifications.payment_events import requeue_failed_payment_emails

logger = logging.getLogger(__name__)


def create_worker_provider() -> EmailProvider:
    """Build a delivery provider and reject local sinks that discard queued messages."""
    provider_name = os.getenv("EMAIL_PROVIDER", "console")
    provider = create_email_provider(
        provider_name,
        app_env=os.getenv("APP_ENV", "development"),
        resend_api_key=os.getenv("RESEND_API_KEY"),
        from_address=os.getenv("EMAIL_FROM_ADDRESS"),
        smtp_host=os.getenv("SMTP_HOST"),
        smtp_port=os.getenv("SMTP_PORT", "587"),
        smtp_username=os.getenv("SMTP_USERNAME"),
        smtp_password=os.getenv("SMTP_PASSWORD"),
        smtp_use_ssl=os.getenv("SMTP_USE_SSL", "false"),
    )
    if provider.name not in {"resend", "smtp"}:
        raise RuntimeError(
            "Email worker requires Resend or SMTP; console/capture are test sinks"
        )
    return provider


async def run_worker() -> None:
    """Poll committed outbox rows; run as a private worker process, never an HTTP endpoint."""
    provider = create_worker_provider()
    poll_seconds = max(1, min(int(os.getenv("EMAIL_WORKER_POLL_SECONDS", "10")), 300))
    retry_request_id = os.getenv("EMAIL_REQUEUE_REQUEST_ID", "").strip()
    if retry_request_id:
        try:
            async with AsyncSessionLocal() as session:
                restored = await requeue_failed_payment_emails(session, retry_request_id)
            logger.info(
                "EMAIL_REQUEUE_COMPLETED",
                extra={"request_id": retry_request_id, "template_count": restored},
            )
        except Exception as exc:  # noqa: BLE001 - leave normal delivery worker available.
            logger.error(
                "EMAIL_REQUEUE_FAILED",
                extra={"request_id": retry_request_id, "error_type": type(exc).__name__},
            )
    logger.info("email_outbox_worker_started", extra={"provider": provider.name})
    while True:
        try:
            async with AsyncSessionLocal() as session:
                delivered = await EmailOutboxService(session).deliver_due(provider, limit=20)
            if delivered:
                continue
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - worker must survive transient DB errors.
            logger.error(
                "email_outbox_worker_iteration_failed",
                extra={"error_type": type(exc).__name__},
            )
        await asyncio.sleep(poll_seconds)


def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
