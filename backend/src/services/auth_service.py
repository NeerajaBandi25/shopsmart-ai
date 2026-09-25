"""Authentication service for user registration, login, logout."""

import asyncio
import math
import re
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import AuthenticationError, ConflictError, RateLimitError, ValidationError
from src.core.observability import security_audit_event
from src.core.rate_limiter import (
    check_login_rate_limit,
    record_failed_attempt,
    record_successful_login,
)
from src.core.security import generate_csrf_token, hash_password, verify_password
from src.models.user import User
from src.repositories.user_repository import UserRepository

LOGIN_RATE_LIMIT_MAX_ATTEMPTS = 5
LOGIN_RATE_LIMIT_WINDOW_MINUTES = 15


class AuthService:
    """Service for authentication operations."""

    def __init__(self, db: AsyncSession):
        """Initialize service.

        Args:
            db: Database session
        """
        self.db = db
        self.user_repo = UserRepository(db=db)

    async def register_user(self, email: str, password: str) -> dict:
        """Register new user with email and password.

        Args:
            email: User email address
            password: User password (plaintext)

        Returns:
            dict: {user_id, email, created_at}

        Raises:
            ValidationError (400): Invalid email or weak password
            ConflictError (409): Email already exists
        """
        # Validate email format (RFC 5322 simplified)
        if not self._is_valid_email(email):
            security_audit_event("registration_failure", success=False, reason="invalid_email")
            raise ValidationError(
                message="Invalid email format",
                error_code="invalid_email",
            )

        # Validate password strength
        if not self._is_strong_password(password):
            security_audit_event("registration_failure", success=False, reason="weak_password")
            raise ValidationError(
                message="Password must be at least 8 characters and contain uppercase, lowercase, digit, and special character",
                error_code="weak_password",
            )

        # Check for duplicate email
        existing_user = await self.user_repo.get_user_by_email(email)
        if existing_user:
            security_audit_event("registration_failure", success=False, reason="email_exists")
            raise ConflictError(
                message="Email already in use",
                error_code="email_already_exists",
            )

        # Hash password
        password_hash = hash_password(password)

        # Create user
        user = await self.user_repo.create_user(
            email=email,
            password_hash=password_hash,
        )

        await self.db.commit()

        security_audit_event(
            "registration_success", success=True, user_id=str(user.id)
        )

        return {
            "user_id": str(user.id),
            "email": user.email,
            "created_at": user.created_at.isoformat(),
        }

    async def login_user(
        self, email: str, password: str, ip_address: str, user_agent: str
    ) -> dict:
        """Authenticate user and create session with single-session enforcement.

        Args:
            email: User email address
            password: User password (plaintext)
            ip_address: Client IP address
            user_agent: Client user agent

        Returns:
            dict: {session_id, user_id, email}

        Raises:
            AuthenticationError (401): Invalid credentials
            RateLimitError (429): Rate limit exceeded
        """
        # Import repositories inside method to avoid circular imports
        from src.repositories.login_attempt_repository import LoginAttemptRepository
        from src.repositories.session_repository import SessionRepository
        from src.repositories.user_repository import UserRepository

        # Initialize repositories
        user_repo = UserRepository(db=self.db)
        session_repo = SessionRepository(db=self.db)
        login_attempt_repo = LoginAttemptRepository(db=self.db)

        # LoginAttempt rows remain the durable audit trail; the limiter provides
        # shared Redis state when available and process-local fallback otherwise.
        # The Redis client is synchronous, so run its calls outside the event loop.
        is_rate_limited = await asyncio.to_thread(check_login_rate_limit, ip_address)
        if is_rate_limited:
            await login_attempt_repo.log_attempt(
                email=email, ip_address=ip_address, success=False, failure_reason="rate_limit"
            )
            await self.db.commit()
            failed_attempt_timestamps = await login_attempt_repo.get_failed_attempt_timestamps(
                ip_address, minutes=LOGIN_RATE_LIMIT_WINDOW_MINUTES
            )
            if failed_attempt_timestamps:
                attempts_to_expire = max(
                    1,
                    len(failed_attempt_timestamps) - LOGIN_RATE_LIMIT_MAX_ATTEMPTS + 1,
                )
                reset_at = failed_attempt_timestamps[attempts_to_expire - 1] + timedelta(
                    minutes=LOGIN_RATE_LIMIT_WINDOW_MINUTES, microseconds=1
                )
                if reset_at.tzinfo is None:
                    reset_at = reset_at.replace(tzinfo=timezone.utc)
            else:
                reset_at = datetime.now(timezone.utc) + timedelta(
                    minutes=LOGIN_RATE_LIMIT_WINDOW_MINUTES
                )
            security_audit_event(
                "login_rate_limited",
                success=False,
                client_ip=ip_address,
                user_agent=user_agent,
                reason="attempt_limit_exceeded",
            )
            raise RateLimitError(
                limit=LOGIN_RATE_LIMIT_MAX_ATTEMPTS,
                remaining=0,
                reset_at=math.ceil(reset_at.timestamp()),
            )

        # 2. SELECT user BY email; if not found or password wrong → log LoginAttempt(success=FALSE, reason) → raise AuthenticationError (401)
        user = await user_repo.get_user_by_email(email)
        if not user or not verify_password(password, user.password_hash):
            await login_attempt_repo.log_attempt(
                email=email, ip_address=ip_address, success=False, failure_reason="invalid_credentials"
            )
            await self.db.commit()
            await asyncio.to_thread(record_failed_attempt, ip_address)
            security_audit_event(
                "login_failure",
                success=False,
                client_ip=ip_address,
                user_agent=user_agent,
                reason="invalid_credentials",
            )
            raise AuthenticationError()

        # 3. SELECT user FOR UPDATE (row-level lock on user row, prevents concurrent session race)
        # Note: SQLAlchemy ORM with async session doesn't have direct FOR UPDATE in get_user_by_email
        # We'll need to lock the user row explicitly
        locked_user_result = await self.db.execute(
            select(User).where(User.id == user.id).with_for_update()
        )
        locked_user = locked_user_result.scalar_one_or_none()

        if not locked_user:
            # This should not happen if we just fetched the user, but handle gracefully
            await login_attempt_repo.log_attempt(
                email=email, ip_address=ip_address, success=False, failure_reason="user_not_found"
            )
            await self.db.commit()
            await asyncio.to_thread(record_failed_attempt, ip_address)
            security_audit_event(
                "login_failure",
                success=False,
                client_ip=ip_address,
                user_agent=user_agent,
                reason="user_unavailable",
            )
            raise AuthenticationError("Invalid credentials")

        # 4. Invalidate existing active session if present: UPDATE sessions SET is_active=FALSE WHERE user_id=? AND is_active=TRUE
        await session_repo.invalidate_user_sessions(user.id)

        # 5. INSERT new Session with is_active=TRUE, last_activity=now, ip_address, user_agent,
        # DB-backed csrf_token bound to this exact session row.
        session = await session_repo.create_session(
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            csrf_token=generate_csrf_token(),
        )

        # 6. COMMIT transaction (lock released)
        await self.db.commit()

        # D2: successful LoginAttempt must also be committed; the commit above
        # only persists the session/invalidation, so commit the audit row separately.
        # 7. Log LoginAttempt(success=TRUE)
        await login_attempt_repo.log_attempt(
            email=email, ip_address=ip_address, success=True, failure_reason=None
        )
        await self.db.commit()
        await asyncio.to_thread(record_successful_login, ip_address)

        security_audit_event(
            "login_success",
            success=True,
            user_id=str(user.id),
            client_ip=ip_address,
            user_agent=user_agent,
        )

        # Returns session_id, user_id, email (session_id in cookie only, never in response body)
        return {
            "session_id": str(session.id),
            "user_id": str(user.id),
            "email": user.email,
        }

    async def logout_user(self, session_id: str) -> bool:
        """Logout user by invalidating their session.

        Args:
            session_id: Session ID to invalidate

        Returns:
            bool: True if session was invalidated, False if session not found
        """
        # Import repository inside method to avoid circular imports
        from src.repositories.session_repository import SessionRepository

        # Initialize repository
        session_repo = SessionRepository(db=self.db)

        # D5: session invalidation is flush-only in the repository, so the
        # service must commit; otherwise logout is lost on session close.
        # Invalidate the session
        result = await session_repo.invalidate_session(session_id)

        if result:
            await self.db.commit()

        return result

    async def change_password(
        self, user_id: UUID, current_password: str, new_password: str
    ) -> None:
        """Change user password and invalidate all sessions (rotate CSRF).

        Args:
            user_id: Authenticated user ID (from validated session)
            current_password: Current password (plaintext, verified)
            new_password: New password (strength-validated)

        Raises:
            ValidationError (400): incorrect current password or weak new password
        """
        from src.repositories.session_repository import SessionRepository

        user = await self.user_repo.get_user_by_id(user_id)
        if not user or not verify_password(current_password, user.password_hash):
            security_audit_event(
                "password_change_failure",
                success=False,
                user_id=str(user_id),
                reason="current_password_invalid",
            )
            raise ValidationError(
                message="Current password is incorrect",
                error_code="invalid_current_password",
            )
        if not self._is_strong_password(new_password):
            security_audit_event(
                "password_change_failure",
                success=False,
                user_id=str(user_id),
                reason="new_password_weak",
            )
            raise ValidationError(
                message=(
                    "New password must be at least 8 characters with uppercase, "
                    "lowercase, digit, and special character"
                ),
                error_code="weak_password",
            )
        user.password_hash = hash_password(new_password)
        session_repo = SessionRepository(db=self.db)
        await session_repo.invalidate_user_sessions(user.id)
        await self.db.commit()
        security_audit_event(
            "password_change_success", success=True, user_id=str(user.id)
        )

    @staticmethod
    def _is_valid_email(email: str) -> bool:
        """Validate email format per RFC 5322 (simplified).

        Args:
            email: Email address to validate

        Returns:
            bool: True if valid, False otherwise
        """
        if not email or len(email) > 254:
            return False

        # Simplified RFC 5322 pattern
        pattern = r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$"
        return bool(re.match(pattern, email))

    @staticmethod
    def _is_strong_password(password: str) -> bool:
        """Validate password strength.

        Requirements:
        - At least 8 characters
        - Contains uppercase letter
        - Contains lowercase letter
        - Contains digit
        - Contains special character

        Args:
            password: Password to validate

        Returns:
            bool: True if strong, False otherwise
        """
        if not password or len(password) < 8:
            return False

        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(not c.isalnum() for c in password)

        return has_upper and has_lower and has_digit and has_special
