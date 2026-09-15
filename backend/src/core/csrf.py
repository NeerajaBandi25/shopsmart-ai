"""CSRF protection module."""

import secrets
from datetime import datetime, timedelta
from typing import Optional


class CSRFTokenManager:
    """Manage CSRF tokens with expiration."""

    def __init__(self, token_lifetime_hours: int = 24):
        """Initialize CSRF token manager.

        Args:
            token_lifetime_hours: How long CSRF tokens are valid (default 24 hours)
        """
        self.token_lifetime = timedelta(hours=token_lifetime_hours)
        self._tokens: dict[str, dict] = {}  # token -> {expires_at, session_id}

    def generate_token(self, session_id: str) -> str:
        """Generate new CSRF token for session.

        Args:
            session_id: Session ID to associate with token

        Returns:
            str: CSRF token
        """
        token = secrets.token_hex(32)
        self._tokens[token] = {
            "session_id": session_id,
            "expires_at": datetime.utcnow() + self.token_lifetime,
        }
        return token

    def validate_token(self, token: str, session_id: str) -> bool:
        """Validate CSRF token.

        Args:
            token: CSRF token from request
            session_id: Session ID to validate against

        Returns:
            bool: True if token is valid and not expired
        """
        if token not in self._tokens:
            return False

        token_data = self._tokens[token]

        # Check expiration
        if datetime.utcnow() > token_data["expires_at"]:
            del self._tokens[token]
            return False

        # Check session match
        if token_data["session_id"] != session_id:
            return False

        return True

    def revoke_token(self, token: str) -> None:
        """Revoke a CSRF token (e.g., after logout).

        Args:
            token: CSRF token to revoke
        """
        self._tokens.pop(token, None)

    def cleanup_expired_tokens(self) -> None:
        """Remove expired tokens from store."""
        now = datetime.utcnow()
        expired = [
            token
            for token, data in self._tokens.items()
            if now > data["expires_at"]
        ]
        for token in expired:
            del self._tokens[token]


# Global CSRF token manager instance
csrf_manager = CSRFTokenManager()
