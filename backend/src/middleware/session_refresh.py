"""Session refresh middleware for updating session activity and cookie expiration."""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from src.core.config import settings
from src.core.session_validator import validate_session
from src.database import AsyncSessionLocal


class SessionRefreshMiddleware(BaseHTTPMiddleware):
    """Middleware to refresh session on authenticated requests."""

    async def dispatch(self, request: Request, call_next):
        # Process the request and get the response
        response = await call_next(request)

        # Only requests that passed the authentication dependency may refresh.
        if not getattr(request.state, "session_authenticated", False):
            return response

        session_id = request.cookies.get("session_id")
        if not session_id:
            return response

        # Validate session and refresh if needed
        # We need to create a new database session for this middleware
        async with AsyncSessionLocal() as db:
            try:
                # Revalidate after the route so revoked or expired sessions never refresh.
                validation_result = await validate_session(session_id, db)

                if validation_result:
                    response.set_cookie(
                        key="session_id",
                        value=session_id,
                        max_age=settings.session_timeout_seconds,
                        path="/",
                        secure=True,
                        httponly=True,
                        samesite="strict",
                    )

            except Exception:
                # If anything goes wrong, don't break the request
                # Just return the original response
                pass

        return response