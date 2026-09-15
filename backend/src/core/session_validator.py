"""Session validation logic with inactivity timeout."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.core.config import settings
from src.models.session import Session


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
        # Fetch session from database
        result = await db_session.execute(
            select(Session)
            .where(Session.id == session_id)
            .with_for_update()
        )
        session = result.scalar_one_or_none()

        if not session:
            return None

        # Check if session is explicitly invalidated (logged out)
        if not session.is_active:
            return None

        # Get user to verify it still exists
        if not session.user:
            return None

        # Check inactivity timeout: NOW() - last_activity > 30 days
        now = datetime.utcnow()
        inactivity_threshold = now.timestamp() - settings.session_timeout_seconds

        if session.last_activity.timestamp() < inactivity_threshold:
            # Session expired due to inactivity
            return None

        # Session is valid - update last_activity to extend timeout
        session.last_activity = now

        await db_session.commit()

        return {
            "user_id": session.user_id,
            "refresh_cookie": True,  # Signal to refresh cookie in response
        }

    except Exception:
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
        result = await db_session.execute(
            select(Session).where(Session.id == session_id)
        )
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
            select(Session)
            .where(Session.user_id == user_id)
            .where(Session.is_active == True)
        )
        sessions = result.scalars().all()

        for session in sessions:
            session.is_active = False

        await db_session.commit()
        return len(sessions)

    except Exception:
        await db_session.rollback()
        return 0
