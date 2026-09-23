"""
Focused tests for run_test ToolAdapter and RunTestExecutor implementation.
"""
import os
import sys
from pathlib import Path

# Ensure .harness is in python path
HARNESS_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(HARNESS_ROOT))

from lib.tool_adapter import normalize_tool_invocation, NormalizedInvocation
from lib.run_test_executor import run_test_invocation


class TestRunTestToolAdapter:
    """Tests for run_test tool adapter normalization."""

    def test_normalize_run_test_valid_target(self):
        """Test normalizing run_test with valid test target."""
        norm = normalize_tool_invocation("run_test", {"test_target": "backend/tests/unit/test_auth_service.py"})
        assert norm is not None
        assert norm.harness_tool_name == "run_test"
        assert norm.invocation_input == {"test_target": "backend/tests/unit/test_auth_service.py"}

    def test_normalize_run_test_valid_test_targets(self):
        """Test that valid test targets (outside src directories) are accepted."""
        valid_targets = [
            "backend/tests/unit/test_auth_service.py",
            "backend/tests/integration/",
            "frontend/tests/",
            "tests/",
            "test_file.py",
            "src/tests/test_example.py"  # Assuming src is not backend/src or frontend/src
        ]
        for target in valid_targets:
            norm = normalize_tool_invocation("run_test", {"test_target": target})
            assert norm is not None, f"Should accept valid test target: {target}"
            assert norm.harness_tool_name == "run_test"
            assert norm.invocation_input["test_target"] == target

    def test_normalize_run_test_with_path_key(self):
        """Test normalizing run_test using 'path' key (backwards compatibility)."""
        norm = normalize_tool_invocation("run_test", {"path": "backend/tests/unit"})
        assert norm is not None
        assert norm.harness_tool_name == "run_test"
        assert norm.invocation_input == {"test_target": "backend/tests/unit"}

    def test_normalize_run_test_with_target_key(self):
        """Test normalizing run_test using 'target' key."""
        norm = normalize_tool_invocation("run_test", {"target": "backend/tests/"})
        assert norm is not None
        assert norm.harness_tool_name == "run_test"
        assert norm.invocation_input == {"test_target": "backend/tests/"}

    def test_normalize_run_test_empty_target_fails_closed(self):
        """Test that empty test_target returns None (DENY)."""
        assert normalize_tool_invocation("run_test", {"test_target": ""}) is None
        assert normalize_tool_invocation("run_test", {"test_target": "   "}) is None
        assert normalize_tool_invocation("run_test", {"test_target": None}) is None
        assert normalize_tool_invocation("run_test", {}) is None

    def test_normalize_run_test_absolute_path_fails_closed(self):
        """Test that absolute paths are rejected."""
        # Windows absolute path
        assert normalize_tool_invocation("run_test", {"test_target": "C:\\\\tests\\\\test.py"}) is None
        # Unix-style absolute path
        assert normalize_tool_invocation("run_test", {"test_target": "/home/user/tests/test.py"}) is None

    def test_normalize_run_test_path_traversal_fails_closed(self):
        """Test that path traversal is rejected."""
        assert normalize_tool_invocation("run_test", {"test_target": "../outside/test.py"}) is None
        assert normalize_tool_invocation("run_test", {"test_target": "backend/../../secret"}) is None
        assert normalize_tool_invocation("run_test", {"test_target": "..\\\\outside\\\\test.py"}) is None

    def test_normalize_run_test_git_path_fails_closed(self):
        """Test that .git paths are rejected."""
        assert normalize_tool_invocation("run_test", {"test_target": ".git/config"}) is None
        assert normalize_tool_invocation("run_test", {"test_target": "path/.git/ignore"}) is None
        assert normalize_tool_invocation("run_test", {"test_target": ".git\\\\config"}) is None

    def test_normalize_run_test_harness_path_fails_closed(self):
        """Test that .harness paths are rejected."""
        assert normalize_tool_invocation("run_test", {"test_target": ".harness/policies/trusted/tool-registry.yaml"}) is None
        assert normalize_tool_invocation("run_test", {"test_target": "path/.harness/config"}) is None
        assert normalize_tool_invocation("run_test", {"test_target": ".harness\\\\lib\\\\tool_adapter.py"}) is None

    def test_normalize_run_test_backend_src_path_fails_closed(self):
        """Test that backend/src/** paths are rejected (source files, not test targets)."""
        assert normalize_tool_invocation("run_test", {"test_target": "backend/src/main.py"}) is None
        assert normalize_tool_invocation("run_test", {"test_target": "backend/src/services/auth_service.py"}) is None
        assert normalize_tool_invocation("run_test", {"test_target": "backend/src/core/exceptions.py"}) is None

    def test_normalize_run_test_frontend_src_path_fails_closed(self):
        """Test that frontend/src/** paths are rejected (source files, not test targets)."""
        assert normalize_tool_invocation("run_test", {"test_target": "frontend/src/lib/api-client.ts"}) is None
        assert normalize_tool_invocation("run_test", {"test_target": "frontend/src/components/login-form.tsx"}) is None

    def test_normalize_run_test_invalid_input_types_fail_closed(self):
        """Test that invalid input types return None."""
        assert normalize_tool_invocation(None, {"test_target": "test.py"}) is None
        assert normalize_tool_invocation("run_test", None) is None
        assert normalize_tool_invocation("run_test", "string_input") is None
        assert normalize_tool_invocation(123, {"test_target": "test.py"}) is None


class TestRunTestExecutor:
    """Tests for run_test executor (when policies allow execution)."""

    def test_run_test_executor_structure(self):
        """Test that run_test_invocation has correct structure and validation."""
        # Test with invalid input (not dict)
        result = run_test_invocation("invalid")
        assert result["success"] is False
        assert result["exit_code"] == -3  # Validation error
        assert "Invalid invocation input" in result["stderr"]

        # Test with missing test_target
        result = run_test_invocation({})
        assert result["success"] is False
        assert result["exit_code"] == -3  # Validation error
        assert "Invalid or missing test_target" in result["stderr"]

        # Test with non-string test_target
        result = run_test_invocation({"test_target": 123})
        assert result["success"] is False
        assert result["exit_code"] == -3  # Validation error
        assert "Invalid or missing test_target" in result["stderr"]

    def test_run_test_executor_security_validation(self):
        """Test that executor performs security validation."""
        # Test absolute path rejection
        result = run_test_invocation({"test_target": "C:\\\\tests\\\\test.py"})
        assert result["success"] is False
        assert result["exit_code"] == -3  # Validation error
        assert "Absolute paths not allowed" in result["stderr"]

        # Test path traversal rejection
        result = run_test_invocation({"test_target": "../outside/test.py"})
        assert result["success"] is False
        assert result["exit_code"] == -3  # Validation error
        assert "Path traversal not allowed" in result["stderr"]

        # Test .git path rejection
        result = run_test_invocation({"test_target": ".git/config"})
        assert result["success"] is False
        assert result["exit_code"] == -3  # Validation error
        assert ".git paths not allowed" in result["stderr"]

        # Test .harness path rejection
        result = run_test_invocation({"test_target": ".harness/config"})
        assert result["success"] is False
        assert result["exit_code"] == -3  # Validation error
        assert ".harness paths not allowed" in result["stderr"]

    def test_run_test_executor_return_structure(self):
        """Test that successful execution returns correct structure."""
        # We can't easily test actual test execution without knowing what tests exist,
        # but we can verify the return structure is correct for both success and failure cases

        # Test with a target that likely doesn't exist (should fail but return proper structure)
        result = run_test_invocation({"test_target": "nonexistent_test_file.py"})

        # Check that all required fields are present
        required_fields = ["success", "exit_code", "test_target", "stdout", "stderr", "execution_time_ms", "timed_out"]
        for field in required_fields:
            assert field in result, f"Missing field: {field}"

        # Check types
        assert isinstance(result["success"], bool)
        assert isinstance(result["exit_code"], int)
        assert isinstance(result["test_target"], str)
        assert isinstance(result["stdout"], str)
        assert isinstance(result["stderr"], str)
        assert isinstance(result["execution_time_ms"], int)
        assert isinstance(result["timed_out"], bool)

        # Check that test_target is preserved
        assert result["test_target"] == "nonexistent_test_file.py"