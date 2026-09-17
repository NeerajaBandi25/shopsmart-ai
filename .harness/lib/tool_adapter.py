"""
Tool Adapter: Maps Claude Code tool invocations to normalized harness actions.

Security Invariants:
1. The model must never supply or choose its own risk class or operation type.
2. The adapter deterministically maps known Claude Code tools to registered harness tools.
3. Unmapped tools, missing required parameters, or malformed inputs return None (failing closed to DENY).
4. No arbitrary command execution is permitted.
"""

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

    # Unsupported command execution tools (e.g. Bash), agent/workflow tools, or unknown tools -> None (DENY)
    return None
