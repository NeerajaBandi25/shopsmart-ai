"""Periodic cleanup for payment reservations whose provider session was never linked."""

import asyncio
import logging
import re

from src.core.payment_limits import PAYMENT_RESERVATION_SWEEP_INTERVAL_SECONDS
from src.database import AsyncSessionLocal
from src.services.payment_provider import get_payment_provider
from src.services.payment_service import (
    expire_abandoned_failed_payment_reservations,
    expire_unlinked_payment_reservations,
    reconcile_stale_linked_payment_sessions,
)

logger = logging.getLogger(__name__)

_DATABASE_ERROR_CATEGORIES = {
    "08000": "database_connection_error",
    "08003": "database_connection_error",
    "08006": "database_connection_error",
    "23505": "unique_violation",
    "40001": "serialization_failure",
    "40P01": "deadlock",
    "42501": "insufficient_privilege",
    "42P01": "undefined_table",
    "3F000": "invalid_schema",
}
_DATABASE_ERROR_PREFIXES = {
    "08": "database_connection_error",
    "22": "database_data_error",
    "23": "database_integrity_error",
    "42": "database_sql_error",
}
_DATABASE_URL_PATTERN = re.compile(r"(?i)\b(postgres(?:ql)?(?:\+\w+)?://)[^@\s]+@")
_SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)([a-z0-9_.-]*(?:password|passwd|secret|token|api[_-]?key)\s*[:=]\s*)"
    r"(\"[^\"]*\"|'[^']*'|[^\s,;]+)"
)


def safe_worker_error_context(error: Exception) -> dict[str, str]:
    """Describe a sweeper failure without logging SQL statements or credentials."""
    original = getattr(error, "orig", None)
    cause = original or error
    sqlstate = (
        getattr(cause, "sqlstate", None)
        or getattr(cause, "pgcode", None)
        or getattr(getattr(cause, "diag", None), "sqlstate", None)
    )
    module = type(cause).__module__.lower()
    is_database_error = original is not None or module.startswith(
        ("asyncpg", "psycopg", "sqlalchemy")
    )
    category = _DATABASE_ERROR_CATEGORIES.get(str(sqlstate), "")
    if not category and sqlstate:
        category = _DATABASE_ERROR_PREFIXES.get(str(sqlstate)[:2], "database_error")
    if not category:
        category = "database_error" if is_database_error else "worker_error"

    message = re.sub(r"\s+", " ", str(cause)).strip()
    message = _DATABASE_URL_PATTERN.sub(r"\1[redacted]@", message)
    message = _SECRET_ASSIGNMENT_PATTERN.sub(r"\1[redacted]", message)
    return {
        "exception_type": type(error).__name__[:80],
        "error_category": category,
        "error_message": message[:240] or "No exception message provided",
    }


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
        except Exception as error:
            logger.exception(
                "payment_reservation_sweep_failed",
                extra={
                    "event": "PAYMENT_RESERVATION_SWEEP_FAILED",
                    **safe_worker_error_context(error),
                },
            )
        await asyncio.sleep(PAYMENT_RESERVATION_SWEEP_INTERVAL_SECONDS)
