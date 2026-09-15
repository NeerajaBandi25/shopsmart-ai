"""Authentication API routes."""

from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.deps import get_db
from src.services.auth_service import AuthService


# ============================================================================
# Request/Response Models
# ============================================================================


class RegisterRequest(BaseModel):
    """Registration request model."""

    email: str = Field(..., min_length=1, description="User email address")
    password: str = Field(..., min_length=1, description="User password")


class RegisterResponse(BaseModel):
    """Registration response model."""

    user_id: str = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    created_at: str = Field(..., description="Account creation timestamp")


# ============================================================================
# Routes
# ============================================================================

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user",
)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> RegisterResponse:
    """Register new user with email and password.

    Args:
        request: Registration request with email and password
        db: Database session

    Returns:
        RegisterResponse: User ID, email, and creation timestamp

    Raises:
        ValidationError (400): Invalid email or weak password
        ConflictError (409): Email already exists
    """
    auth_service = AuthService(db=db)
    result = await auth_service.register_user(
        email=request.email,
        password=request.password,
    )

    return RegisterResponse(**result)
