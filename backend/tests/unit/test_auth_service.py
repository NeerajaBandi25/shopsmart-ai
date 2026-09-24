"""Unit tests for authentication service (TDD)."""

import pytest
from uuid import UUID

from src.core.exceptions import ValidationError, ConflictError, AuthenticationError, RateLimitError
from src.services.auth_service import AuthService
from src.repositories.user_repository import UserRepository
from src.repositories.session_repository import SessionRepository
from src.repositories.login_attempt_repository import LoginAttemptRepository


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


# ============================================================================
# User Story 2 Tests: Login (T042-T044)
# ============================================================================


class TestLoginValidation:
    """T042: Test login validation."""

    async def test_login_with_correct_credentials(
        self, auth_service: AuthService, test_user_data_in_db: dict, test_db
    ):
        """Login with correct email and password should succeed."""
        email = test_user_data_in_db["email"]
        password = test_user_data_in_db["password"]

        result = await auth_service.login_user(
            email=email,
            password=password,
            ip_address="127.0.0.1",
            user_agent="test-agent",
        )

        assert "session_id" in result
        # Get the actual user ID from the database to compare
        from src.repositories.user_repository import UserRepository
        user_repo = UserRepository(db=test_db)
        user = await user_repo.get_user_by_email(email)
        assert result["user_id"] == str(user.id)
        assert result["email"] == email

    async def test_login_with_incorrect_password(
        self, auth_service: AuthService, test_user_data_in_db: dict
    ):
        """Login with incorrect password should raise AuthenticationError (401)."""
        email = test_user_data_in_db["email"]
        wrong_password = "WrongPassword123!"

        with pytest.raises(AuthenticationError) as exc_info:
            await auth_service.login_user(
                email=email,
                password=wrong_password,
                ip_address="127.0.0.1",
                user_agent="test-agent",
            )
        assert exc_info.value.status_code == 401
        assert exc_info.value.error_code == "invalid_credentials"
        # Should be generic message, not revealing whether email exists
        assert exc_info.value.message == "Invalid email or password"

    async def test_login_with_nonexistent_email(
        self, auth_service: AuthService
    ):
        """Login with non-existent email should raise AuthenticationError (401)."""
        email = "nonexistent@example.com"
        password = "anyPassword123!"

        with pytest.raises(AuthenticationError) as exc_info:
            await auth_service.login_user(
                email=email,
                password=password,
                ip_address="127.0.0.1",
                user_agent="test-agent",
            )
        assert exc_info.value.status_code == 401
        assert exc_info.value.error_code == "invalid_credentials"
        # Should be generic message, not revealing whether email exists
        assert exc_info.value.message == "Invalid email or password"


class TestSingleSessionEnforcement:
    """T043: Test single-session enforcement."""

    async def test_second_login_invalidates_previous_session(
        self, auth_service: AuthService, test_user_data_in_db: dict, test_db
    ):
        """Second login from different device should invalidate previous session."""
        from src.repositories.session_repository import SessionRepository

        email = test_user_data_in_db["email"]
        password = test_user_data_in_db["password"]

        # First login
        result1 = await auth_service.login_user(
            email=email,
            password=password,
            ip_address="127.0.0.1",
            user_agent="test-agent-1",
        )
        session1_id = result1["session_id"]

        # Verify first session exists and is active
        session_repo = SessionRepository(db=test_db)
        session1 = await session_repo.get_session(session1_id)
        assert session1 is not None
        assert session1.is_active is True

        # Second login (different device)
        result2 = await auth_service.login_user(
            email=email,
            password=password,
            ip_address="127.0.0.2",  # Different IP
            user_agent="test-agent-2",
        )
        session2_id = result2["session_id"]

        # Verify second session exists and is active
        session2 = await session_repo.get_session(session2_id)
        assert session2 is not None
        assert session2.is_active is True
        assert session2_id != session1_id

        # Verify first session is now invalidated
        session1_after = await session_repo.get_session(session1_id)
        assert session1_after is not None
        assert session1_after.is_active is False  # Should be invalidated

    async def test_only_one_active_session_per_user(
        self, auth_service: AuthService, test_user_data_in_db: dict, test_db
    ):
        """After multiple logins, only one active session should exist per user."""
        from src.repositories.session_repository import SessionRepository

        email = test_user_data_in_db["email"]
        password = test_user_data_in_db["password"]

        # Perform three logins
        result1 = await auth_service.login_user(
            email=email,
            password=password,
            ip_address="127.0.0.1",
            user_agent="test-agent-1",
        )
        result2 = await auth_service.login_user(
            email=email,
            password=password,
            ip_address="127.0.0.2",
            user_agent="test-agent-2",
        )
        result3 = await auth_service.login_user(
            email=email,
            password=password,
            ip_address="127.0.0.3",
            user_agent="test-agent-3",
        )

        # Check all sessions exist
        session_repo = SessionRepository(db=test_db)
        session1 = await session_repo.get_session(result1["session_id"])
        session2 = await session_repo.get_session(result2["session_id"])
        session3 = await session_repo.get_session(result3["session_id"])

        assert session1 is not None
        assert session2 is not None
        assert session3 is not None

        # Only the most recent session should be active
        assert session1.is_active is False
        assert session2.is_active is False
        assert session3.is_active is True


class TestRateLimitingLogic:
    """T044: Test rate limiting logic."""

    async def test_five_failed_attempts_allowed(
        self, auth_service: AuthService
    ):
        """Up to 5 failed login attempts from same IP should be allowed."""
        email = "nonexistent@example.com"  # Use non-existent email to guarantee failure
        password = "wrong123!"
        ip_address = "192.168.1.100"

        # Try 5 failed attempts - all should fail with AuthenticationError, not RateLimitError
        for i in range(5):
            with pytest.raises(AuthenticationError) as exc_info:
                await auth_service.login_user(
                    email=email,
                    password=password,
                    ip_address=ip_address,
                    user_agent="test-agent",
                )
            assert exc_info.value.status_code == 401
            assert exc_info.value.error_code == "invalid_credentials"

    async def test_sixth_failed_attempt_rate_limited(
        self, auth_service: AuthService
    ):
        """6th failed login attempt from same IP should raise RateLimitError (429)."""
        email = "nonexistent@example.com"  # Use non-existent email to guarantee failure
        password = "wrong123!"
        ip_address = "192.168.1.100"

        # Try 5 failed attempts first
        for i in range(5):
            with pytest.raises(AuthenticationError):
                await auth_service.login_user(
                    email=email,
                    password=password,
                    ip_address=ip_address,
                    user_agent="test-agent",
                )

        # 6th attempt should be rate limited
        with pytest.raises(RateLimitError) as exc_info:
            await auth_service.login_user(
                email=email,
                password=password,
                ip_address=ip_address,
                user_agent="test-agent",
            )
        assert exc_info.value.status_code == 429
        assert exc_info.value.error_code == "rate_limited"

    async def test_rate_limit_resets_after_time_window(self, test_db):
        """The limiter allows attempts again after its shared window expires."""
        from datetime import timedelta

        from freezegun import freeze_time

        from src.core import rate_limiter as rate_limiter_module
        from src.services.auth_service import AuthService

        # Test user credentials
        email = "rate_limit_reset@example.com"
        password = "wrong123!"
        ip_address = "192.168.1.100"

        auth_service = AuthService(db=test_db)

        with freeze_time("2025-01-01 12:00:00") as clock:
            rate_limiter_module.rate_limiter._clock = lambda: clock().timestamp()
            for _ in range(5):
                with pytest.raises(AuthenticationError):
                    await auth_service.login_user(
                        email=email,
                        password=password,
                        ip_address=ip_address,
                        user_agent="test-agent",
                    )

            with pytest.raises(RateLimitError):
                await auth_service.login_user(
                    email=email,
                    password=password,
                    ip_address=ip_address,
                    user_agent="test-agent",
                )

            clock.tick(delta=timedelta(minutes=15, seconds=1))
            with pytest.raises(AuthenticationError):
                await auth_service.login_user(
                    email=email,
                    password=password,
                    ip_address=ip_address,
                    user_agent="test-agent",
                )


# ============================================================================
# User Story 3 Tests: Logout (T059-T062)
# ============================================================================

class TestLogout:
    """T059: Test logout invalidation."""

    async def test_logout_invalidation(self, auth_service: AuthService, user_repo: UserRepository, test_db):
        """Test logout invalidation: session is_active set to FALSE; subsequent session lookup fails"""
        # Create a user
        password = "Secure123!"
        user_result = await auth_service.register_user(
            email="logout_test@example.com", password=password
        )

        # Login to create a session
        login_result = await auth_service.login_user(
            email="logout_test@example.com",
            password=password,
            ip_address="127.0.0.1",
            user_agent="test-agent",
        )
        session_id = login_result["session_id"]

        # Verify session exists and is active
        session_repo = SessionRepository(db=test_db)
        session = await session_repo.get_session(session_id)
        assert session is not None
        assert session.is_active is True

        # Logout the user
        await auth_service.logout_user(session_id)

        # Verify session is now invalidated
        session_after = await session_repo.get_session(session_id)
        assert session_after is not None
        assert session_after.is_active is False


# ============================================================================
# User Story 4 Tests: Authenticated User Identity & Authorization Boundaries (T069-T075)
# ============================================================================