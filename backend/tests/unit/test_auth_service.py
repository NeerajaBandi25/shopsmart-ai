"""Unit tests for authentication service (TDD)."""

import pytest
from uuid import UUID

from src.core.exceptions import ValidationError, ConflictError
from src.services.auth_service import AuthService
from src.repositories.user_repository import UserRepository


@pytest.fixture
def auth_service(test_db):
    """Create AuthService with test database."""
    return AuthService(db=test_db)


@pytest.fixture
def user_repo(test_db):
    """Create UserRepository with test database."""
    return UserRepository(db=test_db)


# ============================================================================
# User Story 1 Tests: Registration (T028-T031)
# ============================================================================


class TestRegistrationValidation:
    """T028: Test registration validation - email format per RFC 5322."""

    async def test_valid_email_formats(self, auth_service):
        """Valid emails should be accepted."""
        valid_emails = [
            "user@example.com",
            "test.user@example.co.uk",
            "user+tag@example.com",
            "test_user@sub.example.com",
        ]
        for email in valid_emails:
            result = await auth_service.register_user(
                email=email, password="Secure123!"
            )
            assert result["email"] == email
            assert "user_id" in result
            assert isinstance(result["user_id"], (str, UUID))

    async def test_invalid_email_formats(self, auth_service):
        """Invalid emails should raise ValidationError (400)."""
        invalid_emails = [
            "notanemail",
            "@example.com",
            "user@",
            "user @example.com",
            "",
        ]
        for email in invalid_emails:
            with pytest.raises(ValidationError) as exc_info:
                await auth_service.register_user(email=email, password="Secure123!")
            assert exc_info.value.status_code == 400


class TestPasswordStrengthEnforcement:
    """T029: Test password strength enforcement."""

    async def test_weak_passwords_rejected(self, auth_service):
        """Weak passwords (too short, missing criteria) should raise ValidationError (400)."""
        weak_passwords = [
            "123",  # too short
            "password",  # no uppercase, digit, special char
            "PASSWORD123",  # no lowercase, special char
            "Pass123",  # no special character
            "Pass!word",  # no digit
        ]
        for password in weak_passwords:
            with pytest.raises(ValidationError) as exc_info:
                await auth_service.register_user(
                    email="test@example.com", password=password
                )
            assert exc_info.value.status_code == 400

    async def test_strong_password_accepted(self, auth_service):
        """Strong passwords (≥8 chars, uppercase, lowercase, digit, special) should succeed."""
        result = await auth_service.register_user(
            email="test@example.com", password="Secure123!"
        )
        assert "user_id" in result
        assert result["email"] == "test@example.com"


class TestDuplicateEmailPrevention:
    """T030: Test duplicate email prevention."""

    async def test_duplicate_email_raises_conflict(self, auth_service):
        """Second registration with same email returns ConflictError (409)."""
        email = "duplicate@example.com"

        # First registration should succeed
        result1 = await auth_service.register_user(
            email=email, password="Secure123!"
        )
        assert result1["email"] == email

        # Second registration with same email should fail
        with pytest.raises(ConflictError) as exc_info:
            await auth_service.register_user(email=email, password="Secure456!")
        assert exc_info.value.status_code == 409

    async def test_different_emails_allowed(self, auth_service):
        """Multiple registrations with different emails should succeed."""
        result1 = await auth_service.register_user(
            email="user1@example.com", password="Secure123!"
        )
        result2 = await auth_service.register_user(
            email="user2@example.com", password="Secure456!"
        )
        assert result1["user_id"] != result2["user_id"]


class TestPasswordHashing:
    """T031: Test password hashing with bcrypt."""

    async def test_password_hashing(self, auth_service, user_repo):
        """Registered password should be hashed with bcrypt, never plaintext."""
        email = "hash_test@example.com"
        password = "PlainPassword123!"

        result = await auth_service.register_user(email=email, password=password)
        user_id = UUID(result["user_id"])

        # Fetch user from database
        user = await user_repo.get_user_by_id(user_id)

        # Password hash should not equal plaintext
        assert user.password_hash != password
        # Password hash should start with bcrypt prefix
        assert user.password_hash.startswith("$2b$")

    async def test_verify_password_correct(self, auth_service, user_repo):
        """verify_password should return True for correct password."""
        email = "verify_correct@example.com"
        password = "CorrectPassword123!"

        result = await auth_service.register_user(email=email, password=password)
        user_id = UUID(result["user_id"])

        user = await user_repo.get_user_by_id(user_id)

        # Import security module for verification
        from src.core.security import verify_password

        assert verify_password(password, user.password_hash) is True

    async def test_verify_password_incorrect(self, auth_service, user_repo):
        """verify_password should return False for incorrect password."""
        email = "verify_incorrect@example.com"
        password = "CorrectPassword123!"

        result = await auth_service.register_user(email=email, password=password)
        user_id = UUID(result["user_id"])

        user = await user_repo.get_user_by_id(user_id)

        # Import security module for verification
        from src.core.security import verify_password

        assert verify_password("WrongPassword456!", user.password_hash) is False
