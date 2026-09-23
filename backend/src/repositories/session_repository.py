"""Session repository for data access."""

from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.session import Session


class SessionRepository:
    """Repository for Session entity data access."""

    def __init__(self, db: AsyncSession):
        """Initialize repository.

        Args:
            db: Database session
        """
        self.db = db

    async def create_session(
        self,
        user_id: UUID,
        ip_address: str,
        user_agent: str,
        csrf_token: str,
    ) -> Session:
        """Create new session.

        Args:
            user_id: User ID
            ip_address: Client IP address
            user_agent: Client user agent
            csrf_token: DB-backed CSRF token for this session

        Returns:
            Session: Created session object
        """
        session = Session(
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            is_active=True,
            csrf_token=csrf_token,
        )
        self.db.add(session)
        await self.db.flush()
        return session

    async def get_session(self, session_id: str) -> Session | None:
        """Get session by ID.

        Args:
            session_id: Session ID

        Returns:
            Session | None: Session object or None if not found
        """
        from uuid import UUID
        try:
            session_uuid = UUID(session_id)
        except ValueError:
            return None

        result = await self.db.execute(
            select(Session).where(Session.id == session_uuid)
        )
        return result.scalar_one_or_none()

    async def update_session_activity(self, session_id: str) -> bool:
        """Update session last_activity timestamp.

        Args:
            session_id: Session ID

        Returns:
            bool: True if updated, False if not found
        """
        from uuid import UUID
        try:
            session_uuid = UUID(session_id)
        except ValueError:
            return False

        result = await self.db.execute(
            select(Session).where(Session.id == session_uuid)
        )
        session = result.scalar_one_or_none()

        if not session:
            return False

        from datetime import datetime
        session.last_activity = datetime.utcnow()
        await self.db.flush()
        return True

    async def invalidate_session(self, session_id: str) -> bool:
        """Invalidate session (mark as inactive).

        Args:
            session_id: Session ID

        Returns:
            bool: True if invalidated, False if not found
        """
        from uuid import UUID
        try:
            session_uuid = UUID(session_id)
        except ValueError:
            return False

        result = await self.db.execute(
            select(Session).where(Session.id == session_uuid)
        )
        session = result.scalar_one_or_none()

        if not session:
            return False

        session.is_active = False
        await self.db.flush()
        return True

    async def invalidate_user_sessions(self, user_id: UUID) -> int:
        """Invalidate all active sessions for user.

        Args:
            user_id: User ID

        Returns:
            int: Number of sessions invalidated
        """
        result = await self.db.execute(
            select(Session).where(
                and_(
                    Session.user_id == user_id,
                    Session.is_active == True,
                )
            )
        )
        sessions = result.scalars().all()

        for session in sessions:
            session.is_active = False

        await self.db.flush()
        return len(sessions)

    async def get_active_session(self, user_id: UUID) -> Session | None:
        """Get active session for user (single-session enforcement).

        Args:
            user_id: User ID

        Returns:
            Session | None: Active session or None
        """
        result = await self.db.execute(
            select(Session).where(
                and_(
                    Session.user_id == user_id,
                    Session.is_active == True,
                )
            )
        )
        return result.scalar_one_or_none()
