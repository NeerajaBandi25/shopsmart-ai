"""User profile/password routes (canonical password-change contract)."""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.deps import get_current_user, get_db, require_csrf_token
from src.core.exceptions import AuthenticationError
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
    current_user_uuid: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _csrf_validated: None = Depends(require_csrf_token),
):
    """Change password after session authentication and CSRF validation."""
    service = AuthService(db=db)
    await service.change_password(
        user_id=current_user_uuid,
        current_password=body.current_password,
        new_password=body.new_password,
    )
    return None
