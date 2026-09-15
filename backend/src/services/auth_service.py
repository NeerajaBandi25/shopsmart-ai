"""Authentication service for user registration, login, logout."""

import logging
import re
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import ValidationError, ConflictError
from src.core.security import hash_password, verify_password
from src.repositories.user_repository import UserRepository

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
