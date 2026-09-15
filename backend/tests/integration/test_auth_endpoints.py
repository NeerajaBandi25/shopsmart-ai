"""Integration tests for authentication endpoints (TDD)."""

import pytest
from httpx import AsyncClient


# ============================================================================
# User Story 1 Tests: Registration Endpoint (T032-T035)
# ============================================================================


class TestRegistrationEndpoint:
    """T032: Test registration endpoint POST /api/v1/auth/register."""

    async def test_registration_success(self, test_client: AsyncClient, test_db):
        """POST /api/v1/auth/register with valid email/password returns 201."""
        response = await test_client.post(
            "/api/v1/auth/register",
            json={"email": "newuser@example.com", "password": "Secure123!"},
        )

        assert response.status_code == 201
        data = response.json()
        assert "user_id" in data
        assert data["email"] == "newuser@example.com"
        assert "created_at" in data
        # User record should exist in database
        from src.repositories.user_repository import UserRepository

        user_repo = UserRepository(db=test_db)
        user = await user_repo.get_user_by_email("newuser@example.com")
        assert user is not None

    async def test_registration_invalid_email(self, test_client: AsyncClient):
        """POST /api/v1/auth/register with invalid email returns 400."""
        response = await test_client.post(
            "/api/v1/auth/register",
            json={"email": "notanemail", "password": "Secure123!"},
        )

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "error_code" in data

    async def test_registration_weak_password(self, test_client: AsyncClient):
        """POST /api/v1/auth/register with weak password returns 400."""
        response = await test_client.post(
            "/api/v1/auth/register",
            json={"email": "user@example.com", "password": "weak"},
        )

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "error_code" in data

    async def test_registration_duplicate_email(
        self, test_client: AsyncClient, test_user_data_in_db
    ):
        """POST /api/v1/auth/register with duplicate email returns 409."""
        # User already exists from test_user_data_in_db fixture
        email = test_user_data_in_db["email"]

        response = await test_client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "Secure123!"},
        )

        assert response.status_code == 409
        data = response.json()
        assert "detail" in data
        assert "error_code" in data


class TestRegistrationErrorCases:
    """T033: Test registration error cases."""

    async def test_missing_email_field(self, test_client: AsyncClient):
        """Missing email field returns 422 (validation error)."""
        response = await test_client.post(
            "/api/v1/auth/register",
            json={"password": "Secure123!"},
        )

        assert response.status_code == 422

    async def test_missing_password_field(self, test_client: AsyncClient):
        """Missing password field returns 422 (validation error)."""
        response = await test_client.post(
            "/api/v1/auth/register",
            json={"email": "user@example.com"},
        )

        assert response.status_code == 422

    async def test_validation_error_includes_error_code(
        self, test_client: AsyncClient
    ):
        """Validation errors include error_code field."""
        response = await test_client.post(
            "/api/v1/auth/register",
            json={"email": "invalid", "password": "weak"},
        )

        assert response.status_code == 400
        data = response.json()
        assert "error_code" in data
        assert isinstance(data["error_code"], str)


class TestImmediateLoginAfterRegistration:
    """T034: Test immediate login after registration."""

    async def test_login_after_registration(
        self, test_client: AsyncClient, test_db
    ):
        """Registered user can log in with provided credentials (verify password hash)."""
        from src.repositories.user_repository import UserRepository
        from src.core.security import verify_password

        email = "logintest@example.com"
        password = "Secure123!"

        # Register user
        response = await test_client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password},
        )
        assert response.status_code == 201
        user_id = response.json()["user_id"]

        # Verify user was created with correct password hash
        user_repo = UserRepository(db=test_db)
        user = await user_repo.get_user_by_email(email)
        assert user is not None

        # Verify password can be authenticated
        assert verify_password(password, user.password_hash) is True

        # Verify incorrect password fails
        assert verify_password("WrongPassword123!", user.password_hash) is False


class TestRegistrationContractCompliance:
    """T035: Verify registration endpoint contract per contracts/auth-api.md."""

    async def test_registration_response_schema(self, test_client: AsyncClient):
        """Registration response matches contract: {user_id, email, created_at} or error envelope."""
        response = await test_client.post(
            "/api/v1/auth/register",
            json={"email": "contract@example.com", "password": "Secure123!"},
        )

        assert response.status_code == 201
        data = response.json()

        # Verify required fields
        assert "user_id" in data
        assert "email" in data
        assert "created_at" in data

        # Verify field types
        assert isinstance(data["user_id"], str)
        assert isinstance(data["email"], str)
        assert isinstance(data["created_at"], str)

    async def test_error_response_envelope(self, test_client: AsyncClient):
        """Error responses match envelope: {detail, status_code, error_code}."""
        response = await test_client.post(
            "/api/v1/auth/register",
            json={"email": "invalid", "password": "weak"},
        )

        assert response.status_code == 400
        data = response.json()

        # Verify error envelope
        assert "detail" in data
        assert "error_code" in data
        assert isinstance(data["detail"], str)
        assert isinstance(data["error_code"], str)
