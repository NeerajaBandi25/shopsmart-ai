"""Dependency injection for FastAPI endpoints."""

from typing import AsyncGenerator, Optional
from uuid import UUID

from fastapi import Cookie, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import AuthenticationError, AuthorizationError
from src.core.security import verify_csrf_token
from src.core.session_validator import validate_session
from src.database import AsyncSessionLocal
from src.repositories.session_repository import SessionRepository


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
    request: Request,
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

    request.state.session_authenticated = True
    request.state.user_id = str(result["user_id"])
    return result["user_id"]


async def require_csrf_token(
    session_id: Optional[str] = Cookie(None),
    csrf_token: Optional[str] = Header(None, alias="X-CSRF-Token"),
    current_user_uuid: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Require the CSRF token stored on the current authenticated session."""
    if not csrf_token:
        raise AuthorizationError(message="CSRF token missing", error_code="csrf_invalid")
    if not session_id:
        raise AuthenticationError("Session required")

    session = await SessionRepository(db=db).get_session(session_id)
    if (
        not session
        or not session.is_active
        or not session.csrf_token
        or session.user_id != current_user_uuid
    ):
        raise AuthenticationError("Session invalid or expired")
    if not verify_csrf_token(csrf_token, session.csrf_token):
        raise AuthorizationError(message="Invalid CSRF token", error_code="csrf_invalid")
