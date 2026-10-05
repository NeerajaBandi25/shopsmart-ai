"""Periodic cleanup for payment reservations whose provider session was never linked."""

import asyncio
import logging

from src.core.payment_limits import PAYMENT_RESERVATION_SWEEP_INTERVAL_SECONDS
from src.database import AsyncSessionLocal
from src.services.payment_provider import get_payment_provider
from src.services.payment_service import (
    expire_abandoned_failed_payment_reservations,
    expire_unlinked_payment_reservations,
    reconcile_stale_linked_payment_sessions,
)

logger = logging.getLogger(__name__)


async def run_payment_reservation_sweeper() -> None:
    """Release abandoned no-session reservations after the remote-session safety window."""
    logger.info(
        "payment_reservation_sweeper_started",
        extra={"event": "PAYMENT_RESERVATION_SWEEPER_STARTED"},
    )
    while True:
        try:
            async with AsyncSessionLocal() as session:
                await expire_unlinked_payment_reservations(session)
                await expire_abandoned_failed_payment_reservations(session)
                provider = get_payment_provider()
                if provider.is_configured():
                    await reconcile_stale_linked_payment_sessions(session, provider)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "payment_reservation_sweep_failed",
                extra={"event": "PAYMENT_RESERVATION_SWEEP_FAILED"},
            )
        await asyncio.sleep(PAYMENT_RESERVATION_SWEEP_INTERVAL_SECONDS)
