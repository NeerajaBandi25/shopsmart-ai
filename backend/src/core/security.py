"""Security utilities for password hashing and session management."""

import secrets
from uuid import uuid4

import bcrypt

BCRYPT_MAX_PASSWORD_BYTES = 72


def password_fits_bcrypt(password: str) -> bool:
    """Return whether a password has an unambiguous UTF-8 representation for bcrypt."""
    # UTF-8 encodes every Unicode code point to at least one byte. This cheap
    # guard bounds the work before encoding the small remainder for byte count.
    if len(password) > BCRYPT_MAX_PASSWORD_BYTES:
        return False
    try:
        return len(password.encode("utf-8")) <= BCRYPT_MAX_PASSWORD_BYTES
    except UnicodeEncodeError:
        return False


def hash_password(password: str) -> str:
    """Hash password using bcrypt with 12 salt rounds.

    Args:
        password: Plain text password

    Returns:
        str: Hashed password (bcrypt format)
    """
    if not password_fits_bcrypt(password):
        raise ValueError("Password must not exceed 72 UTF-8 bytes")
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain password against bcrypt hash.

    Args:
        plain_password: Plain text password to verify
        hashed_password: Bcrypt hashed password

    Returns:
        bool: True if password matches, False otherwise
    """
    if not password_fits_bcrypt(plain_password):
        return False
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def generate_session_id() -> str:
    """Generate cryptographically random session ID.

    Returns:
        str: Random UUID session identifier
    """
    return str(uuid4())


def generate_csrf_token() -> str:
    """Generate cryptographically random CSRF token.

    Returns:
        str: Random CSRF token (hex string)
    """
    return secrets.token_hex(32)  # 64-character hex string (256 bits)


def verify_csrf_token(token: str, stored_token: str) -> bool:
    """Verify CSRF token using constant-time comparison.

    Args:
        token: CSRF token from request
        stored_token: CSRF token stored on server

    Returns:
        bool: True if tokens match, False otherwise
    """
    return secrets.compare_digest(token, stored_token)
