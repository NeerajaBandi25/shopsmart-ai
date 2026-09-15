"""LoginAttempt repository for audit and rate limiting."""

from datetime import datetime, timedelta

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.login_attempt import LoginAttempt


class LoginAttemptRepository:
    """Repository for LoginAttempt entity data access."""

    def __init__(self, db: AsyncSession):
        """Initialize repository.

        Args:
            db: Database session
        """
        self.db = db

    async def log_attempt(
        self,
        email: str,
        ip_address: str,
        success: bool,
        failure_reason: str | None = None,
    ) -> LoginAttempt:
        """Log login attempt.

        Args:
            email: User email
            ip_address: Client IP address
            success: Whether attempt was successful
            failure_reason: Reason for failure (if unsuccessful)

        Returns:
            LoginAttempt: Created attempt record
        """
        attempt = LoginAttempt(
            email=email,
            ip_address=ip_address,
            success=success,
            failure_reason=failure_reason,
        )
        self.db.add(attempt)
        await self.db.flush()
        return attempt

    async def count_failed_attempts(self, ip_address: str, minutes: int = 15) -> int:
        """Count failed login attempts from IP in last N minutes.

        Args:
            ip_address: Client IP address
            minutes: Time window (default 15)

        Returns:
            int: Number of failed attempts
        """
        cutoff_time = datetime.utcnow() - timedelta(minutes=minutes)

        result = await self.db.execute(
            select(LoginAttempt).where(
                and_(
                    LoginAttempt.ip_address == ip_address,
                    LoginAttempt.attempted_at >= cutoff_time,
                    LoginAttempt.success == False,
                )
            )
        )
        return len(result.scalars().all())
