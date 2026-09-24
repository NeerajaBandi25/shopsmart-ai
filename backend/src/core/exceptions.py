"""Custom exception classes for authentication and authorization."""

from typing import Any, Optional


class AppException(Exception):
    """Base application exception."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: str = "INTERNAL_ERROR",
        detail: Optional[dict[str, Any]] = None,
    ):
        """Initialize exception.

        Args:
            message: Human-readable error message
            status_code: HTTP status code
            error_code: Machine-readable error code
            detail: Optional additional details
        """
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.detail = detail or {}
        super().__init__(self.message)


class ValidationError(AppException):
    """Validation error (400)."""

    def __init__(self, message: str, error_code: str = "VALIDATION_ERROR", detail: Optional[dict] = None):
        super().__init__(
            message=message,
            status_code=400,
            error_code=error_code,
            detail=detail,
        )


class AuthenticationError(AppException):
    """Authentication error (401)."""

    def __init__(self, message: str = "Invalid email or password", error_code: str = "invalid_credentials"):
        super().__init__(
            message=message,
            status_code=401,
            error_code=error_code,
        )


class AuthorizationError(AppException):
    """Authorization error (403)."""

    def __init__(self, message: str = "Access denied", error_code: str = "AUTHORIZATION_ERROR"):
        super().__init__(
            message=message,
            status_code=403,
            error_code=error_code,
        )


class RateLimitError(AppException):
    """Rate limit exceeded (429)."""

    def __init__(
        self,
        limit: int,
        remaining: int,
        reset_at: int,
        message: str = "Too many login attempts. Please try again in 15 minutes.",
        error_code: str = "rate_limited",
    ):
        self.rate_limit_headers = {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(max(0, remaining)),
            "X-RateLimit-Reset": str(reset_at),
        }
        super().__init__(
            message=message,
            status_code=429,
            error_code=error_code,
        )


class ConflictError(AppException):
    """Resource conflict (409)."""

    def __init__(self, message: str = "Resource already exists", error_code: str = "CONFLICT"):
        super().__init__(
            message=message,
            status_code=409,
            error_code=error_code,
        )
