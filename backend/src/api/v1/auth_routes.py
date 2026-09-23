"""Authentication API routes."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.deps import get_current_user, get_db
from src.core.exceptions import AuthenticationError
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


class LoginRequest(BaseModel):
    """Login request model."""

    email: str = Field(..., min_length=1, description="User email address")
    password: str = Field(..., min_length=1, description="User password")


class LoginResponse(BaseModel):
    """Login response model."""

    user_id: str = Field(..., description="User ID")
    email: str = Field(..., description="User email")


class MeResponse(BaseModel):
    """Current user response model."""

    user_id: str = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    created_at: str = Field(..., description="Account creation timestamp")


class CsrfResponse(BaseModel):
    """CSRF token response model."""

    csrf_token: str = Field(..., description="CSRF token for state-changing requests")


# ============================================================================
# Routes
# ============================================================================

router = APIRouter(prefix="/auth")


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


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate user and create session",
)
async def login(
    request: LoginRequest,
    http_request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """Authenticate user and create session.

    Args:
        request: Login request with email and password
        http_request: HTTP request to extract IP and user agent
        response: HTTP response to set cookie
        db: Database session

    Returns:
        LoginResponse: User ID and email

    Raises:
        AuthenticationError (401): Invalid credentials
        RateLimitError (429): Rate limit exceeded
    """
    auth_service = AuthService(db=db)

    # Extract IP address and user agent from request
    ip_address = http_request.client.host if http_request.client else "unknown"
    user_agent = http_request.headers.get("user-agent", "unknown")

    # Call auth service to login user
    result = await auth_service.login_user(
        email=request.email,
        password=request.password,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    # Set session cookie with security flags: httpOnly, Secure, SameSite=Strict, Max-Age=2592000
    cookie_value = f"session_id={result['session_id']}; HttpOnly; Secure; SameSite=Strict; Max-Age=2592000; Path=/"
    response.headers.setdefault("Set-Cookie", cookie_value)

    # Return user info (session_id is in cookie only)
    return LoginResponse(
        user_id=result["user_id"],
        email=result["email"],
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout user and invalidate session",
)
async def logout(
    session_id: str = Cookie(None),
    response: Response = None,
    db: AsyncSession = Depends(get_db),
):
    """Logout user by invalidating their session and clearing the session cookie.

    Args:
        session_id: Session ID from secure httpOnly cookie
        response: HTTP response to clear cookie
        db: Database session

    Returns:
        204 No Content on success
        401 Unauthorized if session is invalid or missing
    """
    # If no session cookie provided, return 401
    if not session_id:
        raise AuthenticationError("Session required")

    # Call auth service to logout user (invalidate session)
    auth_service = AuthService(db=db)
    logged_out = await auth_service.logout_user(session_id)

    # If logout_user returned False, session was not found/invalid
    if not logged_out:
        raise AuthenticationError("Invalid session")

    response.headers["Set-Cookie"] = (
        "session_id=; "
        "HttpOnly; "
        "Secure; "
        "SameSite=Strict; "
        "Path=/; "
        "Max-Age=0; "
        "expires=Thu, 01 Jan 1970 00:00:00 GMT"
    )

    # Return 204 No Content (no response body)
    return None


@router.get(
    "/csrf",
    response_model=CsrfResponse,
    status_code=status.HTTP_200_OK,
    summary="Get CSRF token for current session",
)
async def get_csrf_token(
    session_id: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db),
) -> CsrfResponse:
    """Return the csrf_token belonging to the exact session_id cookie.

    Resolves the current session row by session ID (never by user_id alone),
    verifies it is active/unexpired, and returns its stored token.
    Session failures remain 401.
    """
    if not session_id:
        raise AuthenticationError("Session required")
    from src.repositories.session_repository import SessionRepository

    session_repo = SessionRepository(db=db)
    session = await session_repo.get_session(session_id)
    if not session or not session.is_active:
        raise AuthenticationError("Session invalid or expired")
    # Enforce rolling inactivity window (same 30-day rule as validation).
    from datetime import datetime

    from src.core.config import settings

    now = datetime.utcnow()
    if (
        not session.last_activity
        or (now.timestamp() - session.last_activity.timestamp()) > settings.session_timeout_seconds
    ):
        raise AuthenticationError("Session invalid or expired")
    if not session.csrf_token:
        raise AuthenticationError("Session invalid or expired")
    return CsrfResponse(csrf_token=session.csrf_token)


@router.get(
    "/me",
    response_model=MeResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current authenticated user",
)
async def get_current_user_info(
    current_user_uuid: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MeResponse:
    """Get current authenticated user's information.

    Args:
        current_user_uuid: UUID of the current user (from session validation)
        db: Database session

    Returns:
        MeResponse: User ID, email, and creation timestamp

    Raises:
        AuthenticationError: If session invalid or expired
    """
    # Get user from database to get created_at timestamp
    from src.repositories.user_repository import UserRepository

    user_repo = UserRepository(db=db)
    user = await user_repo.get_user_by_id(current_user_uuid)

    if not user:
        raise AuthenticationError("User not found")

    return MeResponse(
        user_id=str(user.id),
        email=user.email,
        created_at=user.created_at.isoformat(),
    )
