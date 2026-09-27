"""Shared authorization policies for user-owned resources."""

from uuid import UUID

from src.core.exceptions import AuthorizationError


def verify_user_owns_resource(user_id: UUID, resource_owner_id: UUID) -> bool:
    """Raise a generic 403 unless the authenticated user owns the resource."""
    if user_id != resource_owner_id:
        raise AuthorizationError(message="Access denied", error_code="forbidden")
    return True
