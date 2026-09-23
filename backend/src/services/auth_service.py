"""Authentication service for user registration, login, logout."""

import logging
import re
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, select

from src.core.exceptions import ValidationError, ConflictError, AuthenticationError, RateLimitError
from src.core.security import hash_password, verify_password, generate_session_id
from src.models.user import User
from src.repositories.user_repository import UserRepository
from src.repositories.session_repository import SessionRepository
from src.repositories.login_attempt_repository import LoginAttemptRepository

logger = logging.getLogger(__name__)


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
            logger.warning(f"Registration attempt with invalid email: {email}")
            raise ValidationError(
                message="Invalid email format",
                error_code="invalid_email",
            )

        # Validate password strength
        if not self._is_strong_password(password):
            logger.warning(f"Registration attempt with weak password for email: {email}")
            raise ValidationError(
                message="Password must be at least 8 characters and contain uppercase, lowercase, digit, and special character",
                error_code="weak_password",
            )

        # Check for duplicate email
        existing_user = await self.user_repo.get_user_by_email(email)
        if existing_user:
            logger.warning(f"Registration attempt with duplicate email: {email}")
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

        logger.info(f"User registered successfully: {email} (ID: {user.id})")

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
        from src.repositories.user_repository import UserRepository
        from src.repositories.session_repository import SessionRepository
        from src.repositories.login_attempt_repository import LoginAttemptRepository

        # Initialize repositories
        user_repo = UserRepository(db=self.db)
        session_repo = SessionRepository(db=self.db)
        login_attempt_repo = LoginAttemptRepository(db=self.db)

        # Transaction (READ COMMITTED isolation per data-model.md):
        # 1. Check rate limit first
        failed_attempts = await login_attempt_repo.count_failed_attempts(ip_address, minutes=15)
        if failed_attempts >= 5:
            await login_attempt_repo.log_attempt(
                email=email, ip_address=ip_address, success=False, failure_reason="rate_limit"
            )
            logger.warning(f"Rate limit exceeded for IP: {ip_address}")
            raise RateLimitError()

        # 2. SELECT user BY email; if not found or password wrong → log LoginAttempt(success=FALSE, reason) → raise AuthenticationError (401)
        user = await user_repo.get_user_by_email(email)
        if not user or not verify_password(password, user.password_hash):
            await login_attempt_repo.log_attempt(
                email=email, ip_address=ip_address, success=False, failure_reason="invalid_credentials"
            )
            logger.warning(f"Failed login attempt for email: {email} from IP: {ip_address}")
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
            logger.warning(f"User not found during lock for email: {email} from IP: {ip_address}")
            raise AuthenticationError("Invalid credentials")

        # 4. Invalidate existing active session if present: UPDATE sessions SET is_active=FALSE WHERE user_id=? AND is_active=TRUE
        await session_repo.invalidate_user_sessions(user.id)

        # 5. INSERT new Session with is_active=TRUE, last_activity=now, ip_address, user_agent
        session = await session_repo.create_session(
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # 6. COMMIT transaction (lock released)
        await self.db.commit()

        # 7. Log LoginAttempt(success=TRUE)
        await login_attempt_repo.log_attempt(
            email=email, ip_address=ip_address, success=True, failure_reason=None
        )

        logger.info(f"User logged in successfully: {email} (ID: {user.id}) from IP: {ip_address}")

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

        # Invalidate the session
        result = await session_repo.invalidate_session(session_id)

        if result:
            logger.info(f"User logged out successfully: session {session_id} invalidated")
        else:
            logger.warning(f"Logout attempt for non-existent session: {session_id}")

        return result

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
