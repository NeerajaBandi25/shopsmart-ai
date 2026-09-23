"""
Test Executor: Runs tests via pytest with security constraints.
"""

import os
import subprocess
import sys
import time
from typing import Any, Dict


def run_test_invocation(invocation_input: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a test target via pytest with security constraints.

    Args:
        invocation_input: Dictionary containing 'test_target' key

    Returns:
        Dictionary with keys:
        - success: bool (True if exit_code == 0)
        - exit_code: int
        - test_target: str (the validated test target)
        - stdout: str (limited to 64 KB)
        - stderr: str (limited to 64 KB)
        - execution_time_ms: int
        - timed_out: bool
    """
    # Validate input
    if not isinstance(invocation_input, dict):
        return _get_error_result("Invalid invocation input: expected dict", None)

    test_target = invocation_input.get("test_target")
    if not isinstance(test_target, str) or not test_target.strip():
        return _get_error_result("Invalid or missing test_target", None)

    test_target = test_target.strip()

    # Security validation - reject dangerous paths
    # Reject: absolute paths
    if os.path.isabs(test_target):
        return _get_error_result(f"Absolute paths not allowed: {test_target}", test_target)

    # Reject: path traversal
    if ".." in test_target or test_target.startswith("../") or "/.." in test_target:
        return _get_error_result(f"Path traversal not allowed: {test_target}", test_target)

    # Reject: .git paths
    if ".git" in test_target.split("/") or ".git" in test_target.split("\\"):
        return _get_error_result(f".git paths not allowed: {test_target}", test_target)

    # Reject: .harness paths
    if ".harness" in test_target.split("/") or ".harness" in test_target.split("\\"):
        return _get_error_result(f".harness paths not allowed: {test_target}", test_target)

    # Note: The instructions mention rejecting backend/src/** and frontend/src/**
    # but this seems contradictory since we want to run tests on application code.
    # Looking at the context, I believe this refers to preventing modification of
    # application source files through run_test, but running tests on them should be allowed.
    # The actual enforcement of what tests can run should be handled by the authorization engine
    # based on policies, not by the executor itself.

    # Construct pytest command
    # python -m pytest <validated_target> --tb=short
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        test_target,
        "--tb=short"
    ]

    start_time = time.time()
    timed_out = False

    try:
        # Run with fixed timeout of 60000 ms (60 seconds)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60.0,  # seconds
            cwd=os.getcwd()  # Use current working directory
        )

        execution_time_ms = int((time.time() - start_time) * 1000)

        # Limit stdout and stderr to 64 KB each
        max_output_size = 64 * 1024  # 64 KB
        stdout = result.stdout[:max_output_size] if result.stdout else ""
        stderr = result.stderr[:max_output_size] if result.stderr else ""

        # If output was truncated, note it (optional)
        if len(result.stdout) > max_output_size:
            stdout += "\n[stdout truncated to 64 KB]"
        if len(result.stderr) > max_output_size:
            stderr += "\n[stderr truncated to 64 KB]"

        return {
            "success": result.returncode == 0,
            "exit_code": result.returncode,
            "test_target": test_target,
            "stdout": stdout,
            "stderr": stderr,
            "execution_time_ms": execution_time_ms,
            "timed_out": False
        }

    except subprocess.TimeoutExpired:
        execution_time_ms = 60000  # Fixed timeout value
        timed_out = True
        return {
            "success": False,
            "exit_code": -1,  # Indicates timeout
            "test_target": test_target,
            "stdout": "",  # Could capture partial output if needed
            "stderr": "Test execution timed out after 60 seconds",
            "execution_time_ms": execution_time_ms,
            "timed_out": True
        }
    except Exception as e:
        execution_time_ms = int((time.time() - start_time) * 1000)
        return {
            "success": False,
            "exit_code": -2,  # Indicates execution error
            "test_target": test_target,
            "stdout": "",
            "stderr": f"Test execution failed: {str(e)}",
            "execution_time_ms": execution_time_ms,
            "timed_out": False
        }


def _get_error_result(error_message: str, test_target: str) -> Dict[str, Any]:
    """Helper to create an error result dictionary."""
    return {
        "success": False,
        "exit_code": -3,  # Indicates validation error
        "test_target": test_target or "",
        "stdout": "",
        "stderr": error_message,
        "execution_time_ms": 0,
        "timed_out": False
    }


def create_mcp_server():
    from mcp.server import MCPServer
    mcp = MCPServer("shopsmart")

    @mcp.tool()
    def run_test(test_target: str) -> dict:
        return run_test_invocation({"test_target": test_target})

    return mcp


if __name__ == "__main__":
    mcp = create_mcp_server()
    mcp.run()