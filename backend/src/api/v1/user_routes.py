"""User profile/password routes (canonical password-change contract)."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, Header, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.deps import get_current_user, get_db
from src.core.exceptions import AuthenticationError, AuthorizationError
from src.core.security import verify_csrf_token
from src.repositories.session_repository import SessionRepository
from src.repositories.user_repository import UserRepository
from src.services.auth_service import AuthService

router = APIRouter(prefix="/users")


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=1)


class ProfileResponse(BaseModel):
    user_id: str
    email: str
    created_at: str


@router.get("/profile", response_model=ProfileResponse, status_code=status.HTTP_200_OK)
async def get_profile(
    current_user_uuid: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProfileResponse:
    user_repo = UserRepository(db=db)
    user = await user_repo.get_user_by_id(current_user_uuid)
    if not user:
        raise AuthenticationError("User not found")
    return ProfileResponse(
        user_id=str(user.id), email=user.email, created_at=user.created_at.isoformat()
    )


@router.put("/password", status_code=status.HTTP_204_NO_CONTENT, summary="Change password")
async def change_password(
    body: PasswordChangeRequest,
    session_id: Optional[str] = Cookie(None),
    x_csrf_token: Optional[str] = Header(None, alias="X-CSRF-Token"),
    current_user_uuid: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Change password; CSRF failures -> 403, session failures -> 401.

    The CSRF token is compared against the csrf_token stored on the exact
    session row resolved from the session_id cookie (never by user_id alone).
    Success invalidates all sessions, rotating/revoking the token.
    """
    if not session_id:
        raise AuthenticationError("Session required")
    # Missing token is a CSRF failure (403), not an auth failure.
    if not x_csrf_token:
        raise AuthorizationError(message="CSRF token missing", error_code="csrf_invalid")
    session_repo = SessionRepository(db=db)
    session = await session_repo.get_session(session_id)
    if not session or not session.is_active or not session.csrf_token:
        raise AuthenticationError("Session invalid or expired")
    if session.user_id != current_user_uuid:
        raise AuthenticationError("Session invalid or expired")
    if not verify_csrf_token(x_csrf_token, session.csrf_token):
        raise AuthorizationError(message="Invalid CSRF token", error_code="csrf_invalid")

    service = AuthService(db=db)
    await service.change_password(
        user_id=current_user_uuid,
        current_password=body.current_password,
        new_password=body.new_password,
    )
    return None
