"""Session refresh middleware for updating session activity and cookie expiration."""

from typing import Optional
from uuid import UUID

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from src.core.session_validator import validate_session
from src.database import AsyncSessionLocal
from src.models.session import Session
from sqlalchemy import select


class SessionRefreshMiddleware(BaseHTTPMiddleware):
    """Middleware to refresh session on authenticated requests."""

    async def dispatch(self, request: Request, call_next):
        # Process the request and get the response
        response = await call_next(request)

        # Skip session refresh for non-API paths or specific exclusions
        if not request.url.path.startswith("/api/"):
            return response

        # Extract session ID from cookie
        session_id = request.cookies.get("session_id")
        if not session_id:
            # Also check for alternative cookie name
            session_id = request.cookies.get("__session")

        if not session_id:
            return response

        # Validate session and refresh if needed
        # We need to create a new database session for this middleware
        async with AsyncSessionLocal() as db:
            try:
                # Validate session (this will update last_activity if valid)
                validation_result = await validate_session(session_id, db)

                if validation_result:
                    # Session is valid, refresh the cookie
                    # Get the full session object to set proper Max-Age
                    result = await db.execute(
                        select(Session).where(Session.id == session_id)
                    )
                    session = result.scalar_one_or_none()

                    if session:
                        # Set refreshed cookie with same parameters as login
                        cookie_value = (
                            f"session_id={session_id}; "
                            f"HttpOnly; Secure; SameSite=Strict; "
                            f"Max-Age=2592000; Path=/"
                        )
                        response.headers.setdefault("Set-Cookie", cookie_value)

            except Exception:
                # If anything goes wrong, don't break the request
                # Just return the original response
                pass

        return response