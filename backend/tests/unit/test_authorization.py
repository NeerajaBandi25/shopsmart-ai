from uuid import uuid4

import pytest

from src.core.authorization import verify_user_owns_resource
from src.core.exceptions import AuthorizationError


def test_resource_owner_is_authorized():
    owner_id = uuid4()

    assert verify_user_owns_resource(owner_id, owner_id) is True


def test_non_owner_receives_generic_forbidden_error():
    with pytest.raises(AuthorizationError) as exc_info:
        verify_user_owns_resource(uuid4(), uuid4())

    assert exc_info.value.status_code == 403
    assert exc_info.value.error_code == "forbidden"
    assert exc_info.value.message == "Access denied"
