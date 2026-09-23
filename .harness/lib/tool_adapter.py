"""
Tool Adapter: Maps Claude Code tool invocations to normalized harness actions.

Security Invariants:
1. The model must never supply or choose its own risk class or operation type.
2. The adapter deterministically maps known Claude Code tools to registered harness tools.
3. Unmapped tools, missing required parameters, or malformed inputs return None (failing closed to DENY).
4. No arbitrary command execution is permitted.
"""

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional, Set


@dataclass(frozen=True)
class NormalizedInvocation:
    harness_tool_name: str
    invocation_input: Dict[str, Any]


# Set of known Claude Code tool names to their harness equivalents
READ_LIKE_TOOLS: Set[str] = {"Read"}
SEARCH_LIKE_TOOLS: Set[str] = {"Glob", "Grep"}
WRITE_LIKE_TOOLS: Set[str] = {"Edit", "Write", "NotebookEdit"}
TEST_LIKE_TOOLS: Set[str] = {"run_test"}


def normalize_tool_invocation(
    tool_name: Any,
    tool_input: Any,
) -> Optional[NormalizedInvocation]:
    """
    Normalizes a Claude Code tool invocation to a harness tool invocation.

    Returns NormalizedInvocation if tool is recognized and input is valid,
    or None if tool is unknown/unsupported/malformed (fail-closed).
    """
    if not isinstance(tool_name, str) or not tool_name.strip():
        return None

    clean_tool_name = tool_name.strip()

    if not isinstance(tool_input, dict):
        return None

    # Claude Read-like tool -> read_file
    if clean_tool_name in READ_LIKE_TOOLS:
        file_path = tool_input.get("file_path") or tool_input.get("path")
        if not isinstance(file_path, str) or not file_path.strip():
            return None
        return NormalizedInvocation(
            harness_tool_name="read_file",
            invocation_input={"file_path": file_path.strip()},
        )

    # Claude Search-like tool -> search_files
    if clean_tool_name in SEARCH_LIKE_TOOLS:
        invocation_input: Dict[str, Any] = {}
        path_val = tool_input.get("path")
        if isinstance(path_val, str) and path_val.strip():
            invocation_input["path"] = path_val.strip()
        pattern_val = tool_input.get("pattern")
        if isinstance(pattern_val, str) and pattern_val.strip():
            invocation_input["pattern"] = pattern_val.strip()
        return NormalizedInvocation(
            harness_tool_name="search_files",
            invocation_input=invocation_input,
        )

    # Claude Write/Edit-like tool -> apply_patch
    if clean_tool_name in WRITE_LIKE_TOOLS:
        target_path = (
            tool_input.get("file_path")
            or tool_input.get("path")
            or tool_input.get("notebook_path")
        )
        if not isinstance(target_path, str) or not target_path.strip():
            return None
        return NormalizedInvocation(
            harness_tool_name="apply_patch",
            invocation_input={"file_path": target_path.strip()},
        )

    # MCP run_test tool -> run_test
    if clean_tool_name == "mcp__shopsmart__run_test":
        test_target = tool_input.get("test_target")
        if not isinstance(test_target, str) or not test_target.strip():
            return None
        # Validate test target - reject problematic paths
        test_target_stripped = test_target.strip()
        # Reject: non-string/empty targets (already checked above)
        # Reject: absolute paths
        if os.path.isabs(test_target_stripped):
            return None
        # Reject: traversal
        if ".." in test_target_stripped or test_target_stripped.startswith("../") or "/.." in test_target_stripped:
            return None
        # Reject: .git
        if ".git" in test_target_stripped.split("/") or ".git" in test_target_stripped.split("\\"):
            return None
        # Reject: .harness
        if ".harness" in test_target_stripped.split("/") or ".harness" in test_target_stripped.split("\\"):
            return None
        # Note: The MCP tool should follow the same validation as the Claude run_test tool.
        # We reject: backend/src/** and frontend/src/** (these are application source files, not test targets)
        # We reject these because run_test should target test files, not source files directly
        normalized_path = test_target_stripped.replace("\\", "/")  # Normalize for comparison
        if normalized_path.startswith("backend/src/") or normalized_path.startswith("frontend/src/"):
            return None

        return NormalizedInvocation(
            harness_tool_name="run_test",
            invocation_input={"test_target": test_target_stripped},
        )

    # Claude run_test tool -> run_test
    if clean_tool_name in TEST_LIKE_TOOLS:
        test_target = tool_input.get("test_target") or tool_input.get("path") or tool_input.get("target")
        if not isinstance(test_target, str) or not test_target.strip():
            return None
        # Validate test target - reject problematic paths
        test_target_stripped = test_target.strip()
        # Reject: non-string/empty targets (already checked above)
        # Reject: absolute paths
        if os.path.isabs(test_target_stripped):
            return None
        # Reject: traversal
        if ".." in test_target_stripped or test_target_stripped.startswith("../") or "/.." in test_target_stripped:
            return None
        # Reject: .git
        if ".git" in test_target_stripped.split("/") or ".git" in test_target_stripped.split("\\"):
            return None
        # Reject: .harness
        if ".harness" in test_target_stripped.split("/") or ".harness" in test_target_stripped.split("\\"):
            return None
        # Reject: backend/src/** and frontend/src/** (these are application source files, not test targets)
        # We reject these because run_test should target test files, not source files directly
        normalized_path = test_target_stripped.replace("\\", "/")  # Normalize for comparison
        if normalized_path.startswith("backend/src/") or normalized_path.startswith("frontend/src/"):
            return None

        return NormalizedInvocation(
            harness_tool_name="run_test",
            invocation_input={"test_target": test_target_stripped},
        )

    # Unsupported command execution tools (e.g. Bash), agent/workflow tools, or unknown tools -> None (DENY)
    return None
