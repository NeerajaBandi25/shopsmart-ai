"""User repository for data access."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User


class UserRepository:
    """Repository for User entity data access."""

    def __init__(self, db: AsyncSession):
        """Initialize repository.

        Args:
            db: Database session
        """
        self.db = db

    async def create_user(self, email: str, password_hash: str) -> User:
        """Create new user.

        Args:
            email: User email
            password_hash: Hashed password

        Returns:
            User: Created user object
        """
        user = User(email=email, password_hash=password_hash)
        self.db.add(user)
        await self.db.flush()
        return user

    async def get_user_by_email(self, email: str) -> User | None:
        """Get user by email.

        Args:
            email: User email

        Returns:
            User | None: User object or None if not found
        """
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: UUID) -> User | None:
        """Get user by ID.

        Args:
            user_id: User ID

        Returns:
            User | None: User object or None if not found
        """
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def user_exists(self, email: str) -> bool:
        """Check if user with email exists.

        Args:
            email: User email

        Returns:
            bool: True if user exists, False otherwise
        """
        result = await self.db.execute(
            select(User.id).where(User.email == email)
        )
        return result.scalar_one_or_none() is not None
