"""Dependency injection for FastAPI endpoints."""

from typing import AsyncGenerator, Optional
from uuid import UUID

from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import AuthenticationError
from src.core.session_validator import validate_session
from src.database import AsyncSessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide database session to endpoints.

    Services own transaction boundaries (commit); this dependency never
    auto-commits. It only rolls back on exception so failed requests do
    not leave a dirty transaction open.

    Yields:
        AsyncSession: Database session
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def get_current_user(
    session_id: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db),
) -> UUID:
    """Extract and validate current user from session cookie.

    Args:
        session_id: Session ID from secure httpOnly cookie
        db: Database session

    Returns:
        UUID: Authenticated user ID

    Raises:
        AuthenticationError: If session invalid or expired
    """
    if not session_id:
        raise AuthenticationError("Session required")

    result = await validate_session(session_id, db)

    if not result:
        raise AuthenticationError("Session invalid or expired")

    return result["user_id"]
