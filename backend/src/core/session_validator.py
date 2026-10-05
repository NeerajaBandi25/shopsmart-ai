"""Session validation logic with inactivity timeout."""

from datetime import datetime, timedelta, timezone
import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.core.config import settings
from src.core.observability import request_id_context
from src.models.session import Session
from src.models.user import User

_logger = logging.getLogger("shopsmart.session")


async def validate_session(
    session_id: str,
    db_session: AsyncSession,
) -> Optional[dict]:
    """Validate session and check inactivity timeout.

    Rolling inactivity window only (NO absolute cap):
    - Session expires only when NOW() - last_activity > 30 days (2592000 seconds)
    - On each successful validation, last_activity is updated to NOW()
    - This extends timeout to NOW() + 30 days indefinitely
    - Sessions remain valid while user is active

    Args:
        session_id: Session ID from cookie
        db_session: Database session

    Returns:
        dict with user_id and refresh_cookie flag if valid, None if expired/invalid
    """
    try:
        # Fetch session from database (NO FOR UPDATE for ordinary validation)
        try:
            session_uuid = UUID(session_id)
        except ValueError:
            return None

        result = await db_session.execute(select(Session).where(Session.id == session_uuid))
        session = result.scalar_one_or_none()

        if not session:
            return None

        # Check if session is explicitly invalidated (logged out)
        if not session.is_active:
            return None

        # Verify that the user still exists by querying for the user
        user_result = await db_session.execute(select(User.id).where(User.id == session.user_id))
        if not user_result.scalar_one_or_none():
            return None

        # Check inactivity timeout: NOW() - last_activity > 30 days
        now = datetime.now(timezone.utc)
        last_activity = session.last_activity
        # SQLite strips timezone metadata, while PostgreSQL preserves it. Legacy
        # naive values were written as UTC, so normalize them before comparison.
        if last_activity.tzinfo is None:
            last_activity = last_activity.replace(tzinfo=timezone.utc)

        if last_activity < now - timedelta(seconds=settings.session_timeout_seconds):
            # Session expired due to inactivity
            return None

        # Session is valid - update last_activity to extend timeout
        session.last_activity = now

        await db_session.commit()

        return {
            "user_id": session.user_id,
            "refresh_cookie": True,  # Signal to refresh cookie in response
        }
    except SQLAlchemyError as exc:
        # Rollback transaction on database errors to release any locks
        await db_session.rollback()
        _logger.error(
            "session_validation_database_error",
            extra={
                "event": "session_validation_database_error",
                "exception_type": type(exc).__name__,
                "request_id": request_id_context.get(),
            },
        )
        # Treat database errors as invalid sessions (secure fail-closed).
        return None
    except Exception as exc:
        # Rollback transaction on unexpected errors to release any locks
        await db_session.rollback()
        _logger.error(
            "session_validation_unexpected_error",
            extra={
                "event": "session_validation_unexpected_error",
                "exception_type": type(exc).__name__,
                "request_id": request_id_context.get(),
            },
        )
        # Preserve fail-closed behavior while exposing only safe diagnostics.
        return None


async def invalidate_session(
    session_id: str,
    db_session: AsyncSession,
) -> bool:
    """Invalidate a session (on logout).

    Args:
        session_id: Session ID to invalidate
        db_session: Database session

    Returns:
        bool: True if invalidated, False if not found
    """
    try:
        result = await db_session.execute(select(Session).where(Session.id == session_id))
        session = result.scalar_one_or_none()

        if not session:
            return False

        session.is_active = False
        await db_session.commit()
        return True

    except Exception:
        await db_session.rollback()
        return False


async def invalidate_user_sessions(
    user_id: UUID,
    db_session: AsyncSession,
) -> int:
    """Invalidate all sessions for a user (on password change).

    Args:
        user_id: User ID whose sessions to invalidate
        db_session: Database session

    Returns:
        int: Number of sessions invalidated
    """
    try:
        result = await db_session.execute(
            select(Session).where(Session.user_id == user_id).where(Session.is_active.is_(True))
        )
        sessions = result.scalars().all()

        for session in sessions:
            session.is_active = False

        await db_session.commit()
        return len(sessions)

    except Exception:
        await db_session.rollback()
        return 0
