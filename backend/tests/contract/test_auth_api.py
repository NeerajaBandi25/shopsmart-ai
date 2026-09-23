"""Contract tests for authentication API (TDD)."""

import pytest
from httpx import AsyncClient


# ============================================================================
# User Story 2 Tests: Login Endpoint Contract Compliance (T051)
# ============================================================================


class TestLoginEndpointContract:
    """T051: Verify login endpoint contract per contracts/auth-api.md."""

    async def test_login_success_response_schema(
        self, test_client: AsyncClient, test_user_data_in_db: dict
    ):
        """Login success response matches contract: {user_id, email}."""
        email = test_user_data_in_db["email"]
        password = test_user_data_in_db["password"]

        response = await test_client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )

        assert response.status_code == 200
        data = response.json()

        # Verify required fields per contract
        assert "user_id" in data
        assert "email" in data

        # Verify field types
        assert isinstance(data["user_id"], str)
        assert isinstance(data["email"], str)

        # Verify no extra fields that shouldn't be there per contract
        assert "session_id" not in data  # Session ID should be in cookie only
        assert "created_at" not in data  # Not in login response per contract

        # Verify Set-Cookie header is present with correct format
        assert "set-cookie" in response.headers
        cookie_header = response.headers["set-cookie"]
        assert "HttpOnly" in cookie_header
        assert "Secure" in cookie_header
        assert "SameSite=Strict" in cookie_header
        assert "Max-Age=2592000" in cookie_header  # 30 days

    async def test_login_invalid_credentials_error_response(
        self, test_client: AsyncClient
    ):
        """Login with invalid credentials returns 401 with error envelope."""
        response = await test_client.post(
            "/api/v1/auth/login",
            json={"email": "nonexistent@example.com", "password": "wrong123!"},
        )

        assert response.status_code == 401
        data = response.json()

        # Verify error envelope per contract
        assert "detail" in data
        assert "status_code" in data
        assert "error_code" in data

        # Verify field values
        assert isinstance(data["detail"], str)
        assert data["status_code"] == 401
        assert data["error_code"] == "invalid_credentials"

        # Verify generic message (no email existence hints)
        assert data["detail"] == "Invalid email or password"

    async def test_login_rate_limited_error_response(
        self, test_client: AsyncClient
    ):
        """Login with rate limiting returns 429 with error envelope."""
        # Use non-existent email to guarantee failed attempts
        email = "ratelimit_contract_test@example.com"
        password = "wrong123!"

        # Make 5 failed attempts (should return 401)
        for i in range(5):
            response = await test_client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": password},
            )
            assert response.status_code == 401

        # 6th attempt should return 429 (rate limited)
        response = await test_client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        assert response.status_code == 429
        data = response.json()

        # Verify error envelope per contract
        assert "detail" in data
        assert "status_code" in data
        assert "error_code" in data

        # Verify field values
        assert isinstance(data["detail"], str)
        assert data["status_code"] == 429
        assert data["error_code"] == "rate_limited"

        # Verify message
        assert data["detail"] == "Too many login attempts. Please try again in 15 minutes."

    async def test_login_missing_fields_return_422(
        self, test_client: AsyncClient
    ):
        """Login with missing fields returns 422 (validation error)."""
        # Missing email
        response = await test_client.post(
            "/api/v1/auth/login",
            json={"password": "Secure123!"},
        )
        assert response.status_code == 422

        # Missing password
        response = await test_client.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com"},
        )
        assert response.status_code == 422