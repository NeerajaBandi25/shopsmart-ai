"""Standalone transactional email outbox worker (`python -m src.emails.worker`)."""

import asyncio
import logging
import os

from src.database import AsyncSessionLocal
from src.emails.providers import create_email_provider
from src.emails.service import EmailOutboxService

logger = logging.getLogger(__name__)


async def run_worker() -> None:
    """Poll committed outbox rows; run as a private worker process, never an HTTP endpoint."""
    provider_name = os.getenv("EMAIL_PROVIDER", "console")
    app_env = os.getenv("APP_ENV", "development")
    provider = create_email_provider(
        provider_name,
        app_env=app_env,
        resend_api_key=os.getenv("RESEND_API_KEY"),
        mailtrap_api_token=os.getenv("MAILTRAP_API_TOKEN"),
        smtp_url=os.getenv("SMTP_URL"),
    )
    poll_seconds = max(1, min(int(os.getenv("EMAIL_WORKER_POLL_SECONDS", "10")), 300))
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
